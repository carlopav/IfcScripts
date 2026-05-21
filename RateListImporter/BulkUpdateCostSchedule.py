import re
import json

import bpy
from bpy.types import Operator

try:
    from bonsai import tool as _bonsai_tool
    _IfcOperatorBase = (_bonsai_tool.Ifc.Operator, bpy.types.Operator)
    del _bonsai_tool
except Exception:
    _IfcOperatorBase = (bpy.types.Operator,)


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def _match_key(name, identification):
    m = re.search(r'\[([^\]]+)\]', name or '')
    if m:
        return m.group(1)
    return re.sub(r'^([A-Z]+)\d{2}(-)', r'\1\2', identification or '')


# ---------------------------------------------------------------------------
# Value extraction + rate index
# ---------------------------------------------------------------------------

def _get_cost_item_value(cost_item):
    for cv in (cost_item.CostValues or []):
        try:
            v = cv.AppliedValue
            if v is not None:
                return float(v.wrappedValue if hasattr(v, 'wrappedValue') else v)
        except Exception:
            pass
    return 0.0


def _build_rate_index(context):
    """Returns dict: match_key → rate dict from the loaded rate list."""
    index = {}
    for item in context.scene.xml_rate_list:
        rate = json.loads(item.attributes)
        if rate.get("is_parent"):
            continue
        key = _match_key(rate["name"], rate["id"])
        if key and key not in index:
            index[key] = rate
    return index


# ---------------------------------------------------------------------------
# Diff computation
# ---------------------------------------------------------------------------

_preview = {"ordered": [], "to_update": []}


def _compute_diff(context):
    from bonsai import tool
    import ifcopenshell.util.cost
    file = tool.Ifc.get()
    schedule_id = context.scene.BIMCostProperties.active_cost_schedule_id
    schedule = file.by_id(int(schedule_id))
    rate_index = _build_rate_index(context)

    ordered = []
    to_update = []

    def traverse(cost_item):
        key = _match_key(cost_item.Name or '', cost_item.Identification or '')
        if key:
            old_value = _get_cost_item_value(cost_item)
            entry = {
                "ifc_item": cost_item,
                "key": key,
                "identification": cost_item.Identification or '',
                "name": cost_item.Name or '',
                "old_value": old_value,
            }
            if key in rate_index:
                rate = rate_index[key]
                new_value = float(rate["value"])
                entry["rate"] = rate
                entry["new_identification"] = rate["id"]
                entry["new_name"] = rate["name"]
                entry["new_value"] = new_value
                if abs(old_value - new_value) > 1e-6:
                    entry["status"] = "to_update"
                    to_update.append(entry)
                else:
                    entry["status"] = "unchanged"
            else:
                entry["status"] = "not_found"
            ordered.append(entry)

        for rel in (cost_item.IsNestedBy or []):
            for child in rel.RelatedObjects:
                traverse(child)

    for root_item in ifcopenshell.util.cost.get_root_cost_items(schedule):
        traverse(root_item)

    return {"ordered": ordered, "to_update": to_update}


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class BulkUpdateCostSchedule(*_IfcOperatorBase):
    """Update cost item values in the active schedule from the loaded rate list."""

    bl_idname = "bim.bulk_update_cost_schedule"
    bl_label = "Preview & Update from Rate List"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        try:
            has_rates = len(getattr(context.scene, 'xml_rate_list', [])) > 0
            props = context.scene.BIMCostProperties
            return has_rates and props.active_cost_schedule_id != 0
        except Exception:
            return False

    def invoke(self, context, event):
        global _preview
        _preview = _compute_diff(context)
        return context.window_manager.invoke_props_dialog(self, width=560)

    def draw(self, context):
        layout = self.layout
        ordered = _preview["ordered"]
        to_update = _preview["to_update"]

        n_update = sum(1 for e in ordered if e["status"] == "to_update")
        n_unchanged = sum(1 for e in ordered if e["status"] == "unchanged")
        n_not_found = sum(1 for e in ordered if e["status"] == "not_found")

        row = layout.row()
        row.label(text=f"Da aggiornare: {n_update}   Non modificati: {n_unchanged}   Non trovati: {n_not_found}")

        if not to_update:
            layout.label(text="Nessuna modifica da applicare.", icon="INFO")

        box = layout.box()
        for entry in ordered:
            split = box.split(factor=0.28)
            col_id = split.row()
            split2 = split.split(factor=0.52)
            col_name = split2.row()
            col_val = split2.row()

            status = entry["status"]
            col_id.label(text=entry["identification"][:24])
            col_name.label(text=entry["name"][:38])

            if status == "to_update":
                col_val.label(text=f"{entry['old_value']:.2f} → {entry['new_value']:.2f}")
            elif status == "unchanged":
                col_id.enabled = False
                col_name.enabled = False
                col_val.enabled = False
                col_val.label(text="non modificato")
            else:
                col_val.alert = True
                col_val.label(text="non trovato")

    def _execute(self, context):
        from bonsai import tool

        def remove_deep(parent, cost_value):
            for component in list(cost_value.Components or []):
                remove_deep(cost_value, component)
            tool.Ifc.run("cost.remove_cost_value", parent=parent, cost_value=cost_value)

        count = 0
        for entry in _preview["to_update"]:
            ifc_item = entry["ifc_item"]
            rate = entry["rate"]

            for cv in list(ifc_item.CostValues or []):
                remove_deep(ifc_item, cv)

            cost_value = tool.Ifc.run("cost.add_cost_value", parent=ifc_item)

            if float(rate["labor"]) != 0.0:
                tool.Ifc.run("cost.edit_cost_value", cost_value=cost_value, attributes={
                    "AppliedValue": rate["value"],
                    "ArithmeticOperator": "ADD",
                })
                sub1 = tool.Ifc.run("cost.add_cost_value", parent=cost_value)
                sub2 = tool.Ifc.run("cost.add_cost_value", parent=cost_value)
                tool.Ifc.run("cost.edit_cost_value", cost_value=sub1,
                    attributes={"AppliedValue": rate["value"] - rate["labor"]})
                tool.Ifc.run("cost.edit_cost_value", cost_value=sub2,
                    attributes={"Category": "Labor", "AppliedValue": rate["labor"]})
            else:
                tool.Ifc.run("cost.edit_cost_value", cost_value=cost_value,
                    attributes={"AppliedValue": rate["value"]})

            count += 1

        tool.Cost.load_cost_schedule_tree()
        self.report({'INFO'}, f"Updated {count} cost items.")


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------

class BulkUpdatePanel(bpy.types.Panel):
    bl_label = "Bulk Update from Rate List"
    bl_idname = "SCENE_PT_bulk_update_cost_schedule"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Rate List"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        self.layout.operator(BulkUpdateCostSchedule.bl_idname, icon="FILE_REFRESH")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = [
    BulkUpdateCostSchedule,
    BulkUpdatePanel,
]

class_register, class_unregister = bpy.utils.register_classes_factory(classes)


def register():
    class_register()


def unregister():
    class_unregister()


register()
