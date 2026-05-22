import bpy
import re

try:
    from bonsai import tool as _bonsai_tool
    _IfcOperatorBase = (_bonsai_tool.Ifc.Operator, bpy.types.Operator)
    del _bonsai_tool
except Exception:
    _IfcOperatorBase = (bpy.types.Operator,)


# Immutable tuple — Blender caches this; a list would be re-evaluated every redraw
COMPONENT_CATEGORIES = (
    ('SUB_CONTRACT', "Sub-Contract", "Subcontracted works (opere compiute)"),
    ('LABOR',        "Labor",        "Labor costs (manodopera)"),
    ('EQUIPMENT',    "Equipment",    "Equipment rental costs (noli)"),
    ('MATERIAL',     "Material",     "Material costs (materiali)"),
    ('SAFETY',       "Safety",       "Safety costs (oneri sicurezza)"),
)

# Maps Blender enum identifier → IFC Category string stored in the file
_TO_IFC = {
    'SUB_CONTRACT': 'Sub-Contract',
    'LABOR':        'Labor',
    'EQUIPMENT':    'Equipment',
    'MATERIAL':     'Material',
    'SAFETY':       'Safety',
}
# Reverse: IFC Category string → Blender enum identifier
_FROM_IFC = {v: k for k, v in _TO_IFC.items()}

# Canonical write order for IFC output
_CATEGORY_WRITE_ORDER = ['SUB_CONTRACT', 'LABOR', 'EQUIPMENT', 'MATERIAL', 'SAFETY']

_LINE_CATEGORIES = set(_TO_IFC.values())
_OVERHEAD_CAT = "Overhead"
_PROFIT_CAT = "Profit"
_ROUNDING_CAT = "Rounding"
_ALL_PA_CATEGORIES = _LINE_CATEGORIES | {_OVERHEAD_CAT, _PROFIT_CAT, _ROUNDING_CAT}

_IFC_REF_PREFIX = "#ifc:"


# ---------------------------------------------------------------------------
# IFC helpers
# ---------------------------------------------------------------------------

def _get_rate_current_value(file, source_ifc_id):
    """Return the sum of all CostValues for a rate item, or None if no values found."""
    try:
        rate_item = file.by_id(source_ifc_id)
        total = 0.0
        found = False
        for cv in (rate_item.CostValues or []):
            if cv.AppliedValue is not None:
                v = cv.AppliedValue
                total += float(v.wrappedValue if hasattr(v, "wrappedValue") else v)
                found = True
        return total if found else None
    except Exception:
        return None


def _get_totals(wm):
    ct = sum(c.qty * c.unit_price for c in wm.price_analysis_components)
    sg = ct * wm.price_analysis_overhead_pct / 100.0
    profit = (ct + sg) * wm.price_analysis_profit_pct / 100.0
    return ct, sg, profit, ct + sg + profit + wm.price_analysis_rounding


def _get_or_create_unit_entity(file, unit_str):
    for u in file.by_type("IfcContextDependentUnit"):
        if (u.Name or "") == unit_str:
            return u
    dims = file.create_entity(
        "IfcDimensionalExponents",
        LengthExponent=0, MassExponent=0, TimeExponent=0,
        ElectricCurrentExponent=0, ThermodynamicTemperatureExponent=0,
        AmountOfSubstanceExponent=0, LuminousIntensityExponent=0,
    )
    return file.create_entity(
        "IfcContextDependentUnit",
        Dimensions=dims,
        UnitType="USERDEFINED",
        Name=unit_str,
    )


def _set_unit_basis(file, cv, qty, unit_str):
    if not unit_str:
        return False
    try:
        unit_entity = _get_or_create_unit_entity(file, unit_str)
        unit_basis = file.create_entity(
            "IfcMeasureWithUnit",
            ValueComponent=qty,
            UnitComponent=unit_entity,
        )
        cv.UnitBasis = unit_basis
        return True
    except Exception:
        return False


def _read_unit_basis(cv):
    ub = getattr(cv, "UnitBasis", None)
    if ub is None:
        return None, None
    try:
        vc = ub.ValueComponent
        qty = float(vc.wrappedValue if hasattr(vc, "wrappedValue") else vc)
        unit_str = str(getattr(ub.UnitComponent, "Name", None) or "")
        return qty, unit_str
    except Exception:
        return None, None


def _pct_label(label, pct):
    return f"{label} {pct:.1f}%"


def _parse_pct(name):
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", name or "")
    return float(m.group(1)) if m else None


def _remove_analysis_values(tool, cost_item):
    to_remove = [
        cv for cv in (cost_item.CostValues or [])
        if (cv.Category or "") in _ALL_PA_CATEGORIES
    ]
    for cv in to_remove:
        tool.Ifc.run("cost.remove_cost_value", parent=cost_item, cost_value=cv)


# ---------------------------------------------------------------------------
# Property groups
# ---------------------------------------------------------------------------

class PriceAnalysisComponent(bpy.types.PropertyGroup):
    category: bpy.props.EnumProperty(
        name="Category",
        items=COMPONENT_CATEGORIES,
        default='LABOR',
        options={'SKIP_SAVE'},
    )
    description: bpy.props.StringProperty(name="Description", options={'SKIP_SAVE'})
    unit: bpy.props.StringProperty(name="Unit", options={'SKIP_SAVE'})
    qty: bpy.props.FloatProperty(name="Qty", min=0.0, precision=3, default=1.0, options={'SKIP_SAVE'})
    unit_price: bpy.props.FloatProperty(name="Unit Price", min=0.0, precision=2, default=0.0, options={'SKIP_SAVE'})
    source_ifc_id: bpy.props.IntProperty(
        name="Source IFC ID",
        description="Step ID of the source IfcCostItem in the current project (0 = free-form)",
        default=0,
        options={'SKIP_SAVE'},
    )
    source_identification: bpy.props.StringProperty(
        name="Source Identification",
        description="Identification of the source rate item (cached for display)",
        default="",
        options={'SKIP_SAVE'},
    )
    needs_rate_update: bpy.props.BoolProperty(
        name="Rate value has changed",
        default=False,
        options={'SKIP_SAVE'},
    )


# ---------------------------------------------------------------------------
# Operators — list management
# ---------------------------------------------------------------------------

class PA_OT_AddComponent(bpy.types.Operator):
    bl_idname = "price_analysis.add_component"
    bl_label = "Add Free-form Component"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        wm = context.window_manager
        wm.price_analysis_components.add()
        wm.price_analysis_active_index = len(wm.price_analysis_components) - 1
        return {'FINISHED'}


class PA_OT_AddFromRate(bpy.types.Operator):
    bl_idname = "price_analysis.add_from_rate"
    bl_label = "Add Component from Active Cost Item"
    bl_description = (
        "Add the currently selected cost item in the BIM Cost panel as a component. "
        "First use Load to pin the item being analysed, then browse to a rate and click this."
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        try:
            props = context.scene.BIMCostProperties
            if props.active_cost_item is None or props.active_cost_schedule_id == 0:
                return False
            # Disallow adding the pinned target item to itself
            target = context.window_manager.price_analysis_target_ifc_id
            return target == 0 or props.active_cost_item.ifc_definition_id != target
        except Exception:
            return False

    def execute(self, context):
        from bonsai import tool
        wm = context.window_manager
        props = context.scene.BIMCostProperties
        file = tool.Ifc.get()
        rate_item = file.by_id(props.active_cost_item.ifc_definition_id)

        comp = wm.price_analysis_components.add()
        comp.description = rate_item.Name or ""
        comp.qty = 1.0
        comp.category = 'SUB_CONTRACT'
        comp.source_ifc_id = rate_item.id()
        comp.source_identification = rate_item.Identification or ""
        comp.unit_price = _get_rate_current_value(file, rate_item.id()) or 0.0

        wm.price_analysis_active_index = len(wm.price_analysis_components) - 1
        return {'FINISHED'}


class PA_OT_RemoveComponent(bpy.types.Operator):
    bl_idname = "price_analysis.remove_component"
    bl_label = "Remove Component"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        wm = context.window_manager
        comps = wm.price_analysis_components
        idx = wm.price_analysis_active_index
        if 0 <= idx < len(comps):
            comps.remove(idx)
            wm.price_analysis_active_index = max(0, idx - 1)
        return {'FINISHED'}


class PA_OT_MoveUp(bpy.types.Operator):
    bl_idname = "price_analysis.move_up"
    bl_label = "Move Up"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        wm = context.window_manager
        comps = wm.price_analysis_components
        idx = wm.price_analysis_active_index
        if idx > 0:
            comps.move(idx, idx - 1)
            wm.price_analysis_active_index = idx - 1
        return {'FINISHED'}


class PA_OT_MoveDown(bpy.types.Operator):
    bl_idname = "price_analysis.move_down"
    bl_label = "Move Down"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        wm = context.window_manager
        comps = wm.price_analysis_components
        idx = wm.price_analysis_active_index
        if idx < len(comps) - 1:
            comps.move(idx, idx + 1)
            wm.price_analysis_active_index = idx + 1
        return {'FINISHED'}


class PA_OT_ClearAll(bpy.types.Operator):
    bl_idname = "price_analysis.clear_all"
    bl_label = "Clear Analysis"
    bl_description = "Clear all components and reset percentages"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        wm = context.window_manager
        wm.price_analysis_components.clear()
        wm.price_analysis_active_index = 0
        wm.price_analysis_overhead_pct = 15.0
        wm.price_analysis_profit_pct = 10.0
        wm.price_analysis_rounding = 0.0
        wm.price_analysis_target_ifc_id = 0
        wm.price_analysis_item_identification = ""
        wm.price_analysis_item_name = ""
        wm.price_analysis_item_description = ""
        return {'FINISHED'}


class PA_OT_RefreshComponentRate(bpy.types.Operator):
    bl_idname = "price_analysis.refresh_component_rate"
    bl_label = "Update rate value"
    bl_description = "The linked rate value has changed — click to reload the current value"
    bl_options = {'REGISTER', 'UNDO'}

    component_index: bpy.props.IntProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        from bonsai import tool
        wm = context.window_manager
        comps = wm.price_analysis_components
        if not (0 <= self.component_index < len(comps)):
            return {'CANCELLED'}
        comp = comps[self.component_index]
        if not comp.source_ifc_id:
            return {'CANCELLED'}
        file = tool.Ifc.get()
        current = _get_rate_current_value(file, comp.source_ifc_id)
        if current is not None:
            comp.unit_price = current
        try:
            comp.source_identification = file.by_id(comp.source_ifc_id).Identification or ""
        except Exception:
            pass
        comp.needs_rate_update = False
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operators — cost item info
# ---------------------------------------------------------------------------

def _read_cost_item_info(context):
    try:
        from bonsai import tool
        file = tool.Ifc.get()
        wm = context.window_manager
        target_id = wm.price_analysis_target_ifc_id
        if target_id:
            cost_item = file.by_id(target_id)
        else:
            cost_item = file.by_id(context.scene.BIMCostProperties.active_cost_item.ifc_definition_id)
        wm.price_analysis_item_identification = cost_item.Identification or ""
        wm.price_analysis_item_name = cost_item.Name or ""
        wm.price_analysis_item_description = cost_item.Description or ""
    except Exception:
        pass


def _write_cost_item_info(tool, cost_item, wm):
    tool.Ifc.run("cost.edit_cost_item", cost_item=cost_item, attributes={
        "Identification": wm.price_analysis_item_identification or None,
        "Name": wm.price_analysis_item_name or None,
        "Description": wm.price_analysis_item_description or None,
    })


class PA_OT_SyncItemInfo(*_IfcOperatorBase):
    """Re-read Identification, Name and Description from the pinned target item."""
    bl_idname = "price_analysis.sync_item_info"
    bl_label = "Refresh info from IFC"

    @classmethod
    def poll(cls, context):
        return context.window_manager.price_analysis_target_ifc_id != 0

    def _execute(self, context):
        _read_cost_item_info(context)


class PA_OT_ApplyItemInfo(*_IfcOperatorBase):
    """Write Identification, Name and Description to the pinned target item."""
    bl_idname = "price_analysis.apply_item_info"
    bl_label = "Write info to IFC"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.window_manager.price_analysis_target_ifc_id != 0

    def _execute(self, context):
        from bonsai import tool
        import bonsai.bim.module.cost.data
        file = tool.Ifc.get()
        wm = context.window_manager
        cost_item = file.by_id(wm.price_analysis_target_ifc_id)
        _write_cost_item_info(tool, cost_item, wm)
        bonsai.bim.module.cost.data.refresh()
        tool.Cost.load_cost_schedule_tree()


# ---------------------------------------------------------------------------
# Operators — IFC read/write
# ---------------------------------------------------------------------------

class PA_OT_ApplyToIfc(*_IfcOperatorBase):
    """Write the rate analysis to the active IFC cost item."""
    bl_idname = "price_analysis.apply_to_ifc"
    bl_label = "Apply Rate Analysis to IFC"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.window_manager.price_analysis_target_ifc_id != 0

    def _execute(self, context):
        from bonsai import tool
        import bonsai.bim.module.cost.data

        wm = context.window_manager
        file = tool.Ifc.get()
        cost_item = file.by_id(wm.price_analysis_target_ifc_id)

        _write_cost_item_info(tool, cost_item, wm)
        _remove_analysis_values(tool, cost_item)
        ct, sg, profit, final = _get_totals(wm)

        # Line components written in canonical category order
        ordered = sorted(
            wm.price_analysis_components,
            key=lambda c: _CATEGORY_WRITE_ORDER.index(c.category)
            if c.category in _CATEGORY_WRITE_ORDER else len(_CATEGORY_WRITE_ORDER),
        )
        for comp in ordered:
            line_total = round(comp.qty * comp.unit_price, 2)
            cv = tool.Ifc.run("cost.add_cost_value", parent=cost_item)
            tool.Ifc.run("cost.edit_cost_value", cost_value=cv, attributes={
                "Name": comp.description,
                "Category": _TO_IFC[comp.category],
                # AppliedValue = line total (qty × unit_price) so Bonsai sums correctly;
                # UnitBasis keeps qty+unit for round-trip reconstruction on Load
                "AppliedValue": line_total,
            })
            _set_unit_basis(file, cv, comp.qty, comp.unit)
            if comp.source_ifc_id:
                cv.Condition = f"{_IFC_REF_PREFIX}{comp.source_ifc_id}"

        cv_sg = tool.Ifc.run("cost.add_cost_value", parent=cost_item)
        tool.Ifc.run("cost.edit_cost_value", cost_value=cv_sg, attributes={
            "Name": _pct_label("Overhead", wm.price_analysis_overhead_pct),
            "Category": _OVERHEAD_CAT,
            "AppliedValue": round(sg, 2),
        })

        cv_profit = tool.Ifc.run("cost.add_cost_value", parent=cost_item)
        tool.Ifc.run("cost.edit_cost_value", cost_value=cv_profit, attributes={
            "Name": _pct_label("Profit", wm.price_analysis_profit_pct),
            "Category": _PROFIT_CAT,
            "AppliedValue": round(profit, 2),
        })

        if wm.price_analysis_rounding != 0.0:
            cv_r = tool.Ifc.run("cost.add_cost_value", parent=cost_item)
            tool.Ifc.run("cost.edit_cost_value", cost_value=cv_r, attributes={
                "Name": "Rounding",
                "Category": _ROUNDING_CAT,
                "AppliedValue": round(wm.price_analysis_rounding, 2),
            })

        bonsai.bim.module.cost.data.refresh()
        tool.Cost.load_cost_schedule_tree()


class PA_OT_LoadFromIfc(*_IfcOperatorBase):
    """Load rate analysis from the active IFC cost item."""
    bl_idname = "price_analysis.load_from_ifc"
    bl_label = "Load Rate Analysis from IFC"

    @classmethod
    def poll(cls, context):
        try:
            props = context.scene.BIMCostProperties
            return props.active_cost_item is not None and props.active_cost_schedule_id != 0
        except Exception:
            return False

    def _execute(self, context):
        from bonsai import tool

        file = tool.Ifc.get()
        cost_item = file.by_id(context.scene.BIMCostProperties.active_cost_item.ifc_definition_id)
        wm = context.window_manager

        wm.price_analysis_components.clear()
        wm.price_analysis_active_index = 0
        wm.price_analysis_overhead_pct = 15.0
        wm.price_analysis_profit_pct = 10.0
        wm.price_analysis_rounding = 0.0
        wm.price_analysis_target_ifc_id = cost_item.id()
        _read_cost_item_info(context)

        found = False

        for cv in (cost_item.CostValues or []):
            cat = cv.Category or ""

            if cat in _LINE_CATEGORIES:
                found = True
                comp = wm.price_analysis_components.add()
                comp.category = _FROM_IFC.get(cat, 'LABOR')
                comp.description = cv.Name or ""

                # AppliedValue is the line total; unit_price = total / qty
                v = cv.AppliedValue
                line_total = float(v.wrappedValue if hasattr(v, "wrappedValue") else v) if v is not None else 0.0

                qty, unit_str = _read_unit_basis(cv)
                if qty is not None:
                    comp.qty = qty
                    comp.unit = unit_str or ""
                    comp.unit_price = round(line_total / qty, 6) if qty else line_total
                else:
                    comp.unit_price = line_total

                cond = getattr(cv, "Condition", None) or ""
                if cond.startswith(_IFC_REF_PREFIX):
                    try:
                        comp.source_ifc_id = int(cond[len(_IFC_REF_PREFIX):])
                        src = file.by_id(comp.source_ifc_id)
                        comp.source_identification = src.Identification or ""
                    except Exception:
                        pass

                # Check if the linked rate value has changed since last Apply
                if comp.source_ifc_id:
                    current = _get_rate_current_value(file, comp.source_ifc_id)
                    if current is not None and round(current, 2) != round(comp.unit_price, 2):
                        comp.needs_rate_update = True

            elif cat == _OVERHEAD_CAT:
                found = True
                pct = _parse_pct(cv.Name)
                if pct is not None:
                    wm.price_analysis_overhead_pct = pct

            elif cat == _PROFIT_CAT:
                found = True
                pct = _parse_pct(cv.Name)
                if pct is not None:
                    wm.price_analysis_profit_pct = pct

            elif cat == _ROUNDING_CAT:
                found = True
                v = cv.AppliedValue
                if v is not None:
                    wm.price_analysis_rounding = float(
                        v.wrappedValue if hasattr(v, "wrappedValue") else v
                    )

        if not found:
            self.report({'WARNING'}, "No price analysis data found on this cost item.")


# ---------------------------------------------------------------------------
# UI List
# ---------------------------------------------------------------------------

class PriceAnalysisUIList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=False)
        cat_tag = item.category[:3].upper() if item.category else "???"
        row.label(text=f"[{cat_tag}]")
        name_col = row.column()
        name_col.scale_x = 1.6
        if item.source_ifc_id:
            ref_id = item.source_identification or f"#{item.source_ifc_id}"
            name_col.label(text=f"[{ref_id}] {item.description or ''}")
        else:
            name_col.label(text=item.description or "(no description)")
        subtotal = item.qty * item.unit_price
        row.label(text=f"{item.qty:.3g} {item.unit}  ×  {item.unit_price:.2f}  =  {subtotal:.2f}")
        if item.needs_rate_update:
            op = row.operator(
                "price_analysis.refresh_component_rate",
                text="", icon="FILE_REFRESH", emboss=False,
            )
            op.component_index = index


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------

class PriceAnalysisPanel(bpy.types.Panel):
    bl_label = "Rate Analysis"
    bl_idname = "SCENE_PT_price_analysis"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Rate List"

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager

        # Cost item info header
        box = layout.box()
        row = box.row()
        row.label(text="Cost Item", icon="OBJECT_DATA")
        row.operator("price_analysis.sync_item_info", text="", icon="FILE_REFRESH")
        row.operator("price_analysis.apply_item_info", text="", icon="CHECKMARK")
        box.prop(wm, "price_analysis_item_identification", text="ID")
        box.prop(wm, "price_analysis_item_name", text="Name")
        box.prop(wm, "price_analysis_item_description", text="Desc")

        layout.separator(factor=0.5)

        # Toolbar
        row = layout.row(align=True)
        row.operator("price_analysis.add_component", text="", icon="ADD")
        row.operator("price_analysis.add_from_rate", text="", icon="IMPORT")
        row.operator("price_analysis.remove_component", text="", icon="REMOVE")
        row.operator("price_analysis.move_up", text="", icon="TRIA_UP")
        row.operator("price_analysis.move_down", text="", icon="TRIA_DOWN")
        row.separator()
        row.operator("price_analysis.clear_all", text="", icon="TRASH")
        row.separator()
        row.operator("price_analysis.load_from_ifc", text="Load", icon="FILE_REFRESH")
        row.operator("price_analysis.apply_to_ifc", text="Apply", icon="EXPORT")

        # Component list
        layout.template_list(
            "PriceAnalysisUIList", "",
            wm, "price_analysis_components",
            wm, "price_analysis_active_index",
            rows=5,
        )

        # Inline editor for selected component
        comps = wm.price_analysis_components
        idx = wm.price_analysis_active_index
        if 0 <= idx < len(comps):
            comp = comps[idx]
            box = layout.box()
            split = box.split(factor=0.25)
            split.label(text="Category:")
            row = split.row(align=True)
            row.prop_enum(comp, "category", 'SUB_CONTRACT', icon="LINKED")
            row.prop_enum(comp, "category", 'LABOR',        icon="COMMUNITY")
            row.prop_enum(comp, "category", 'EQUIPMENT',    icon="AUTO")
            row.prop_enum(comp, "category", 'MATERIAL',     icon="MATERIAL")
            row.prop_enum(comp, "category", 'SAFETY',       icon="LOCKED")
            box.prop(comp, "description")
            row = box.row(align=True)
            row.prop(comp, "qty")
            row.prop(comp, "unit", text="UM")
            row.prop(comp, "unit_price", text="Unit Price")
            row = box.row()
            row.label(text=f"Subtotal: {comp.qty * comp.unit_price:.2f}")
            if comp.source_ifc_id:
                ref_label = comp.source_identification or f"#{comp.source_ifc_id}"
                row.label(text=f"Rate ref: {ref_label}", icon="LINKED")

        # Summary
        ct, sg, profit, final = _get_totals(wm)
        box = layout.box()

        # Per-category totals (only categories with at least one component)
        cat_totals = {}
        for c in wm.price_analysis_components:
            cat_totals[c.category] = cat_totals.get(c.category, 0.0) + c.qty * c.unit_price
        for cat_id, cat_label, _ in COMPONENT_CATEGORIES:
            total = cat_totals.get(cat_id, 0.0)
            if total:
                split = box.split(factor=0.6)
                split.label(text=f"{cat_label}:")
                split.label(text=f"{total:.2f}")

        box.separator(factor=0.3)

        split = box.split(factor=0.6)
        split.label(text="Technical Cost:")
        split.label(text=f"{ct:.2f}")

        box.separator(factor=0.3)

        split = box.split(factor=0.6)
        split.prop(wm, "price_analysis_overhead_pct", text="Overhead %")
        split.label(text=f"{sg:.2f}")

        split = box.split(factor=0.6)
        split.prop(wm, "price_analysis_profit_pct", text="Profit %")
        split.label(text=f"{profit:.2f}")

        split = box.split(factor=0.6)
        split.prop(wm, "price_analysis_rounding", text="Rounding")
        split.label(text="")

        box2 = layout.box()
        split = box2.split(factor=0.6)
        split.label(text="FINAL PRICE:", icon="FUND")
        split.label(text=f"{final:.2f}")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = [
    PriceAnalysisComponent,
    PriceAnalysisUIList,
    PA_OT_AddComponent,
    PA_OT_AddFromRate,
    PA_OT_RemoveComponent,
    PA_OT_MoveUp,
    PA_OT_MoveDown,
    PA_OT_ClearAll,
    PA_OT_RefreshComponentRate,
    PA_OT_SyncItemInfo,
    PA_OT_ApplyItemInfo,
    PA_OT_ApplyToIfc,
    PA_OT_LoadFromIfc,
    PriceAnalysisPanel,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.WindowManager.price_analysis_components = bpy.props.CollectionProperty(
        type=PriceAnalysisComponent,
    )
    bpy.types.WindowManager.price_analysis_active_index = bpy.props.IntProperty(default=0)
    bpy.types.WindowManager.price_analysis_overhead_pct = bpy.props.FloatProperty(
        name="Overhead %",
        description="Overhead percentage applied to technical cost",
        default=15.0, min=0.0, max=100.0, precision=1,
    )
    bpy.types.WindowManager.price_analysis_profit_pct = bpy.props.FloatProperty(
        name="Profit %",
        description="Profit margin applied to (technical cost + overhead)",
        default=10.0, min=0.0, max=100.0, precision=1,
    )
    bpy.types.WindowManager.price_analysis_rounding = bpy.props.FloatProperty(
        name="Rounding",
        description="Rounding adjustment (positive or negative) added to the final price",
        default=0.0, precision=2,
    )
    bpy.types.WindowManager.price_analysis_item_identification = bpy.props.StringProperty(
        name="Identification", default="",
    )
    bpy.types.WindowManager.price_analysis_item_name = bpy.props.StringProperty(
        name="Name", default="",
    )
    bpy.types.WindowManager.price_analysis_item_description = bpy.props.StringProperty(
        name="Description", default="",
    )
    bpy.types.WindowManager.price_analysis_target_ifc_id = bpy.props.IntProperty(
        name="Target IFC ID",
        description="IFC step ID of the cost item being analysed (0 = none)",
        default=0,
    )


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.WindowManager.price_analysis_components
    del bpy.types.WindowManager.price_analysis_active_index
    del bpy.types.WindowManager.price_analysis_overhead_pct
    del bpy.types.WindowManager.price_analysis_profit_pct
    del bpy.types.WindowManager.price_analysis_rounding
    del bpy.types.WindowManager.price_analysis_item_identification
    del bpy.types.WindowManager.price_analysis_item_name
    del bpy.types.WindowManager.price_analysis_item_description
    del bpy.types.WindowManager.price_analysis_target_ifc_id


register()
