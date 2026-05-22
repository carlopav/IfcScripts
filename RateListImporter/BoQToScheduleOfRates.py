import bpy

try:
    from bonsai import tool as _bonsai_tool
    _IfcOperatorBase = (_bonsai_tool.Ifc.Operator, bpy.types.Operator)
    del _bonsai_tool
except Exception:
    _IfcOperatorBase = (bpy.types.Operator,)


VALID_TYPES = {"UNPRICEDBILLOFQUANTITIES", "PRICEDBILLOFQUANTITIES"}
MAX_DISPLAY = 10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_applied_value(cost_item):
    for cv in (cost_item.CostValues or []):
        try:
            v = cv.AppliedValue
            if v is not None:
                return float(v.wrappedValue if hasattr(v, "wrappedValue") else v)
        except Exception:
            pass
    return None


def _collect_leaf_items(schedule):
    import ifcopenshell.util.cost

    items = []

    def traverse(cost_item):
        children = [child for rel in (cost_item.IsNestedBy or []) for child in rel.RelatedObjects]
        if not children:
            items.append(cost_item)
        for child in children:
            traverse(child)

    for root_item in ifcopenshell.util.cost.get_root_cost_items(schedule):
        traverse(root_item)

    return items


def _build_unique_items(all_items):
    """
    Returns (unique_items, conflicts).
    unique_items: one representative IfcCostItem per (Identification, Name) key.
    conflicts: items sharing a key but differing in Description or applied value.
    """
    groups = {}
    order = []
    for item in all_items:
        key = (item.Identification or "", item.Name or "")
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(item)

    unique_items = []
    conflicts = []

    for key in order:
        items = groups[key]
        if len(items) == 1:
            unique_items.append(items[0])
            continue

        descriptions = {item.Description or "" for item in items}
        values = {_get_applied_value(item) for item in items}

        if len(descriptions) > 1 or len(values) > 1:
            conflicts.append({
                "identification": key[0],
                "name": key[1],
                "count": len(items),
                "descriptions": descriptions,
                "values": values,
            })
        else:
            unique_items.append(items[0])

    return unique_items, conflicts


def _collect_sor_items(schedule):
    """Return all items in the SoR as a list of (key, cost_item) tuples."""
    import ifcopenshell.util.cost

    items = []

    def traverse(cost_item):
        items.append(((cost_item.Identification or "", cost_item.Name or ""), cost_item))
        for rel in (cost_item.IsNestedBy or []):
            for child in rel.RelatedObjects:
                traverse(child)

    for root_item in ifcopenshell.util.cost.get_root_cost_items(schedule):
        traverse(root_item)

    return items


def _diff_text(a, b, label_a="BoQ", label_b="SoR", ctx=30):
    """Compact inline diff: equal segments compressed, changed ones wrapped in « »."""
    import difflib
    a, b = (str(a) if a is not None else ""), (str(b) if b is not None else "")
    if a == b:
        return ""
    out_a, out_b = [], []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        sa, sb = a[i1:i2], b[j1:j2]
        if tag == "equal":
            if len(sa) > ctx * 2:
                sa = sa[:ctx] + "…" + sa[-ctx:]
                sb = sb[:ctx] + "…" + sb[-ctx:]
            out_a.append(sa)
            out_b.append(sb)
        else:
            out_a.append(f"«{sa}»")
            out_b.append(f"«{sb}»")
    return f"{label_a}: " + "".join(out_a) + f"\n{label_b}: " + "".join(out_b)


def _format_diffs(diffs, label_boq="BoQ", label_sor="SoR"):
    parts = []
    for d in diffs:
        if isinstance(d["boq"], str) or isinstance(d["sor"], str):
            parts.append(f"{d['field']}:\n{_diff_text(d['boq'], d['sor'], label_boq, label_sor)}")
        else:
            parts.append(f"{d['field']}:\n  {label_boq}: {d['boq']}\n  {label_sor}: {d['sor']}")
    return "\n\n".join(parts)


def _compare_cost_items(boq_item, sor_item):
    """Returns list of dicts {field, boq, sor} for each differing field (empty if fully congruent)."""
    diffs = []
    boq_desc = boq_item.Description or ""
    sor_desc = sor_item.Description or ""
    if boq_desc != sor_desc:
        diffs.append({"field": "Description", "boq": boq_desc, "sor": sor_desc})
    boq_val = _get_applied_value(boq_item)
    sor_val = _get_applied_value(sor_item)
    if boq_val != sor_val:
        diffs.append({"field": "Value", "boq": boq_val, "sor": sor_val})
    return diffs


def _copy_cost_values(tool, source_item, target_item):
    def copy_cv(source_cv, parent):
        target_cv = tool.Ifc.run("cost.add_cost_value", parent=parent)
        attrs = {}
        if source_cv.AppliedValue is not None:
            try:
                attrs["AppliedValue"] = float(
                    source_cv.AppliedValue.wrappedValue
                    if hasattr(source_cv.AppliedValue, "wrappedValue")
                    else source_cv.AppliedValue
                )
            except Exception:
                pass
        if source_cv.Category:
            attrs["Category"] = source_cv.Category
        if source_cv.ArithmeticOperator:
            attrs["ArithmeticOperator"] = source_cv.ArithmeticOperator
        if attrs:
            tool.Ifc.run("cost.edit_cost_value", cost_value=target_cv, attributes=attrs)
        for component in (source_cv.Components or []):
            copy_cv(component, target_cv)

    for source_cv in (source_item.CostValues or []):
        copy_cv(source_cv, target_item)


def _replace_cost_values(tool, source_item, target_item):
    """Remove all cost values from target_item, then copy from source_item."""
    for cv in list(target_item.CostValues or []):
        tool.Ifc.run("cost.remove_cost_value", parent=target_item, cost_value=cv)
    _copy_cost_values(tool, source_item, target_item)


# ---------------------------------------------------------------------------
# Dynamic enum for existing Schedules of Rates
# ---------------------------------------------------------------------------

def _sor_schedule_items(self, context):
    try:
        from bonsai import tool
        file = tool.Ifc.get()
        if file is None:
            return [("0", "No IFC file loaded", "")]
        schedules = [s for s in file.by_type("IfcCostSchedule") if s.PredefinedType == "SCHEDULEOFRATES"]
        if not schedules:
            return [("0", "No Schedule of Rates found", "")]
        return [(str(s.id()), s.Name or f"#{s.id()}", "") for s in schedules]
    except Exception:
        return [("0", "Error reading IFC file", "")]


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_state = {
    "unique_items": [],
    "conflicts": [],
    "to_add": [],
    "already_present": [],
    "mismatched": [],
    "orphaned": [],
    "resolutions": {},
    "mismatched_tooltips": {},
    "schedule_name": "",
    "total": 0,
    "mode": "NEW",
    "target_schedule_name": "",
}


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------

class BoQToSoROperator(*_IfcOperatorBase):
    """Create or update a Schedule of Rates from the active Bill of Quantities."""

    bl_idname = "bim.boq_to_schedule_of_rates"
    bl_label = "BoQ → Schedule of Rates"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        try:
            props = context.scene.BIMCostProperties
            if props.active_cost_schedule_id == 0:
                return False
            from bonsai import tool
            schedule = tool.Ifc.get().by_id(int(props.active_cost_schedule_id))
            return schedule.PredefinedType in VALID_TYPES
        except Exception:
            return False

    def invoke(self, context, event):
        global _state
        from bonsai import tool

        schedule = tool.Ifc.get().by_id(int(context.scene.BIMCostProperties.active_cost_schedule_id))
        all_items = _collect_leaf_items(schedule)
        unique_items, conflicts = _build_unique_items(all_items)

        mode = context.scene.boq_to_sor_mode
        to_add = unique_items
        already_present = []
        orphaned = []
        mismatched = []
        target_schedule_name = ""

        if mode == "UPDATE":
            target_id = context.scene.boq_to_sor_target_schedule
            if target_id and target_id != "0":
                target_schedule = tool.Ifc.get().by_id(int(target_id))
                target_schedule_name = target_schedule.Name or f"#{target_id}"
                sor_items = _collect_sor_items(target_schedule)
                sor_dict = {}
                for key, item in sor_items:
                    if key not in sor_dict:
                        sor_dict[key] = item
                boq_keys = {(item.Identification or "", item.Name or "") for item in unique_items}
                to_add = []
                already_present = []
                for boq_item in unique_items:
                    key = (boq_item.Identification or "", boq_item.Name or "")
                    if key not in sor_dict:
                        to_add.append(boq_item)
                    else:
                        diffs = _compare_cost_items(boq_item, sor_dict[key])
                        if diffs:
                            mismatched.append({"boq_item": boq_item, "sor_item": sor_dict[key], "diffs": diffs})
                        else:
                            already_present.append(boq_item)
                orphaned = [item for key, item in sor_items if key not in boq_keys]

                sor_by_id = {}
                for (sor_ident, _), sor_item in sor_items:
                    if sor_ident:
                        sor_by_id.setdefault(sor_ident, []).append(sor_item)
                filtered_to_add = []
                for boq_item in to_add:
                    ident = boq_item.Identification or ""
                    matches = sor_by_id.get(ident, []) if ident else []
                    if matches:
                        for sor_item in matches:
                            diffs = [{"field": "Name", "boq": boq_item.Name or "", "sor": sor_item.Name or ""}]
                            diffs.extend(_compare_cost_items(boq_item, sor_item))
                            mismatched.append({"boq_item": boq_item, "sor_item": sor_item, "diffs": diffs})
                    else:
                        filtered_to_add.append(boq_item)
                to_add = filtered_to_add

        _state.update({
            "unique_items": unique_items,
            "conflicts": conflicts,
            "to_add": to_add,
            "already_present": already_present,
            "mismatched": mismatched,
            "orphaned": orphaned,
            "schedule_name": schedule.Name or "(unnamed)",
            "total": len(all_items),
            "mode": mode,
            "target_schedule_name": target_schedule_name,
        })

        return context.window_manager.invoke_props_dialog(self, width=580, confirm_text="Proceed")

    def draw(self, context):
        layout = self.layout
        conflicts = _state["conflicts"]
        to_add = _state["to_add"]
        already_present = _state["already_present"]
        mismatched = _state["mismatched"]
        orphaned = _state["orphaned"]
        unique = _state["unique_items"]
        mode = _state["mode"]
        duplicates = _state["total"] - len(unique) - sum(c["count"] - 1 for c in conflicts)

        layout.label(text=f"Source BoQ: {_state['schedule_name']}")
        if mode == "UPDATE":
            layout.label(text=f"Target SoR: {_state['target_schedule_name']}")

        row = layout.row()
        row.label(text=f"Total leaf items: {_state['total']}")
        row.label(text=f"Unique: {len(unique)}")
        if duplicates:
            row.label(text=f"Duplicates removed: {duplicates}")

        if conflicts:
            layout.separator()
            box = layout.box()
            col = box.column()
            col.alert = True
            col.label(text=f"Conflicts detected ({len(conflicts)}) — operation blocked:", icon="ERROR")
            col.label(text="Items share Identification+Name but differ in Description or value:")
            for c in conflicts:
                row = box.row()
                row.alert = True
                row.label(text=f"[{c['identification']}] {c['name']}  ({c['count']} occurrences)")
                detail = []
                if len(c["descriptions"]) > 1:
                    detail.append("different Description")
                if len(c["values"]) > 1:
                    detail.append(f"different values: {sorted(str(v) for v in c['values'])}")
                if detail:
                    box.label(text="    " + " · ".join(detail))
            return

        layout.separator()

        if mode == "UPDATE":
            row = layout.row()
            row.label(text=f"Rates not present, to be added: {len(to_add)}", icon="ADD")
            row.label(text=f"Rates already present and congruent: {len(already_present)}", icon="CHECKMARK")
            row = layout.row()
            row.label(text=f"Rates present but different: {len(mismatched)}", icon="ERROR" if mismatched else "NONE")
            row.label(text=f"Rates only in Schedule of Rates, not modified: {len(orphaned)}", icon="QUESTION")

            layout.operator(BoQToSoRCopyReportOperator.bl_idname, icon="COPYDOWN")

            if to_add:
                box = layout.box()
                box.label(text="Rates not present, to be added:")
                for item in to_add[:MAX_DISPLAY]:
                    box.label(text=f"  [{item.Identification or ''}] {item.Name or ''}")
                if len(to_add) > MAX_DISPLAY:
                    box.label(text=f"  … and {len(to_add) - MAX_DISPLAY} more")

            if mismatched:
                box = layout.box()
                col = box.column()
                col.alert = True
                col.label(text="Rates present but different (hover for details):")
                for m in mismatched[:MAX_DISPLAY]:
                    item = m["boq_item"]
                    diff_text = _format_diffs(m["diffs"], _state["schedule_name"], _state["target_schedule_name"])
                    op = col.operator(
                        BoQToSoRItemInfoOperator.bl_idname,
                        text=f"[{item.Identification or ''}] {item.Name or ''}",
                        icon="ERROR",
                        emboss=False,
                    )
                    op.diff_text = diff_text
                if len(mismatched) > MAX_DISPLAY:
                    col.label(text=f"  … and {len(mismatched) - MAX_DISPLAY} more")
                layout.operator(BoQToSoRResolveOperator.bl_idname, icon="TOOL_SETTINGS")

            if already_present:
                box = layout.box()
                col = box.column()
                col.enabled = False
                col.label(text="Rates already present and congruent, skipped:")
                for item in already_present[:MAX_DISPLAY]:
                    col.label(text=f"  [{item.Identification or ''}] {item.Name or ''}")
                if len(already_present) > MAX_DISPLAY:
                    col.label(text=f"  … and {len(already_present) - MAX_DISPLAY} more")

            if orphaned:
                box = layout.box()
                col = box.column()
                col.enabled = False
                col.label(text="Rates only in Schedule of Rates, not modified:")
                for item in orphaned[:MAX_DISPLAY]:
                    col.label(text=f"  [{item.Identification or ''}] {item.Name or ''}")
                if len(orphaned) > MAX_DISPLAY:
                    col.label(text=f"  … and {len(orphaned) - MAX_DISPLAY} more")

            if not to_add and not mismatched:
                layout.label(text="Nothing to add — Schedule of Rates is already up to date.", icon="INFO")
        else:
            layout.label(text=f"Items to create: {len(to_add)}", icon="ADD")
            layout.label(text="Click OK to create the new Schedule of Rates.", icon="CHECKMARK")

    def _execute(self, context):
        if _state["conflicts"]:
            self.report({"ERROR"}, f"Operation cancelled: {len(_state['conflicts'])} conflict(s) must be resolved first.")
            return

        from bonsai import tool
        import bonsai.bim.module.cost.data

        to_add = _state["to_add"]

        if not to_add:
            self.report({"INFO"}, "Nothing to add — Schedule of Rates is already up to date.")
            return

        if _state["mode"] == "NEW":
            target_schedule = tool.Ifc.run(
                "cost.add_cost_schedule",
                name=f"SoR - {_state['schedule_name']}",
                predefined_type="SCHEDULEOFRATES",
            )
        else:
            target_schedule = tool.Ifc.get().by_id(int(context.scene.boq_to_sor_target_schedule))

        for source_item in to_add:
            new_item = tool.Ifc.run("cost.add_cost_item", cost_schedule=target_schedule)
            tool.Ifc.run("cost.edit_cost_item", cost_item=new_item, attributes={
                "Name": source_item.Name or "",
                "Identification": source_item.Identification or "",
                "Description": source_item.Description or "",
            })
            _copy_cost_values(tool, source_item, new_item)

        bonsai.bim.module.cost.data.refresh()
        tool.Cost.load_cost_schedule_tree()
        action = "Created" if _state["mode"] == "NEW" else "Updated"
        self.report({"INFO"}, f"{action} '{target_schedule.Name}': {len(to_add)} item(s) added.")


# ---------------------------------------------------------------------------
# Tooltip operator for mismatched items
# ---------------------------------------------------------------------------

class BoQToSoRItemInfoOperator(bpy.types.Operator):
    bl_idname = "bim.boq_to_sor_item_info"
    bl_label = ""
    bl_description = ""

    item_label: bpy.props.StringProperty(default="")
    diff_text: bpy.props.StringProperty(default="")

    @classmethod
    def description(cls, context, properties):
        return properties.diff_text or ""

    def execute(self, context):
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Copy report operator
# ---------------------------------------------------------------------------

class BoQToSoRCopyReportOperator(bpy.types.Operator):
    """Copy the full comparison report to clipboard (tab-separated for LibreOffice)."""

    bl_idname = "bim.boq_to_sor_copy_report"
    bl_label = "Copy Full Report to Clipboard"

    def execute(self, context):
        lines = []
        lines.append(f"Source BoQ\t{_state['schedule_name']}")
        if _state["mode"] == "UPDATE":
            lines.append(f"Target SoR\t{_state['target_schedule_name']}")
        lines.append("")

        to_add = _state["to_add"]
        mismatched = _state["mismatched"]
        already_present = _state["already_present"]
        orphaned = _state["orphaned"]

        if to_add:
            lines.append(f"=== Rates not present, to be added ({len(to_add)}) ===")
            lines.append("Identification\tName")
            for item in to_add:
                lines.append(f"{item.Identification or ''}\t{item.Name or ''}")
            lines.append("")

        if mismatched:
            lines.append(f"=== Rates present but different ({len(mismatched)}) ===")
            lines.append("Identification\tName\tField\tBoQ\tSoR")
            for m in mismatched:
                item = m["boq_item"]
                for d in m["diffs"]:
                    lines.append(f"{item.Identification or ''}\t{item.Name or ''}\t{d['field']}\t{d['boq']}\t{d['sor']}")
            lines.append("")

        if already_present:
            lines.append(f"=== Rates already present and congruent ({len(already_present)}) ===")
            lines.append("Identification\tName")
            for item in already_present:
                lines.append(f"{item.Identification or ''}\t{item.Name or ''}")
            lines.append("")

        if orphaned:
            lines.append(f"=== Rates only in Schedule of Rates, not modified ({len(orphaned)}) ===")
            lines.append("Identification\tName")
            for item in orphaned:
                lines.append(f"{item.Identification or ''}\t{item.Name or ''}")

        context.window_manager.clipboard = "\n".join(lines)
        self.report({"INFO"}, "Report copied to clipboard.")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Per-item resolution: PropertyGroup + UIList + Operator
# ---------------------------------------------------------------------------

class MismatchedRateResolution(bpy.types.PropertyGroup):
    identification: bpy.props.StringProperty()
    rate_name: bpy.props.StringProperty()
    diff_fields: bpy.props.StringProperty()  # short, e.g. "Description · Value"


class COST_UL_MismatchedRates(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type not in {"DEFAULT", "COMPACT"}:
            return
        key = (item.identification, item.rate_name)
        resolution = _state["resolutions"].get(key, "SKIP")
        boq = _state.get("schedule_name") or "BoQ"
        sor = _state.get("target_schedule_name") or "SoR"
        row = layout.row(align=True)
        op = row.operator(
            BoQToSoRItemInfoOperator.bl_idname,
            text=f"[{item.identification}] {item.rate_name}  ({item.diff_fields})",
            icon="CHECKMARK" if resolution != "SKIP" else "ERROR",
            emboss=False,
        )
        op.diff_text = _state["mismatched_tooltips"].get(key, "")
        for label, direction in (("Skip", "SKIP"), (f"{boq}→{sor}", "BOQ_TO_SOR"), (f"{sor}→{boq}", "SOR_TO_BOQ")):
            op = row.operator("bim.boq_to_sor_set_resolution", text=label, depress=(resolution == direction))
            op.identification = item.identification
            op.rate_name = item.rate_name
            op.direction = direction


class BoQToSoRSetResolutionOperator(bpy.types.Operator):
    bl_idname = "bim.boq_to_sor_set_resolution"
    bl_label = ""
    bl_options = {"INTERNAL"}

    identification: bpy.props.StringProperty()
    rate_name: bpy.props.StringProperty()
    direction: bpy.props.StringProperty()

    def execute(self, context):
        _state["resolutions"][(self.identification, self.rate_name)] = self.direction
        return {"FINISHED"}


class BoQToSoRResolveOperator(bpy.types.Operator):
    """Open a scrollable dialog to resolve each mismatched rate individually."""

    bl_idname = "bim.boq_to_sor_resolve"
    bl_label = "Resolve Mismatched Rates"
    bl_options = {"REGISTER", "UNDO"}

    def invoke(self, context, event):
        col = context.scene.boq_to_sor_mismatched_rates
        col.clear()
        _state["resolutions"] = {}
        _state["mismatched_tooltips"] = {}
        for m in _state["mismatched"]:
            boq_item = m["boq_item"]
            entry = col.add()
            entry.identification = boq_item.Identification or ""
            entry.rate_name = boq_item.Name or ""
            entry.diff_fields = " · ".join(d["field"] for d in m["diffs"])
            key = (entry.identification, entry.rate_name)
            _state["resolutions"][key] = "SKIP"
            _state["mismatched_tooltips"][key] = _format_diffs(m["diffs"], _state["schedule_name"], _state["target_schedule_name"])
        return context.window_manager.invoke_props_dialog(self, width=720, confirm_text="Apply")

    def draw(self, context):
        layout = self.layout
        n = len(_state["mismatched"])
        layout.label(text=f"Resolve {n} mismatched rate(s) — hover each row for diff details:")
        layout.template_list(
            "COST_UL_MismatchedRates", "",
            context.scene, "boq_to_sor_mismatched_rates",
            context.scene, "boq_to_sor_mismatched_index",
            rows=min(n, 12),
        )
        idx = context.scene.boq_to_sor_mismatched_index
        rates = context.scene.boq_to_sor_mismatched_rates
        if 0 <= idx < len(rates):
            selected = rates[idx]
            key = (selected.identification, selected.rate_name)
            diff = _state["mismatched_tooltips"].get(key, "")
            if diff:
                box = layout.box()
                for line in diff.split("\n"):
                    box.label(text=line if line else " ")

        boq = _state.get("schedule_name") or "BoQ"
        sor = _state.get("target_schedule_name") or "SoR"
        layout.label(
            text=f"{boq}→{sor} updates the SoR rate.  {sor}→{boq} updates the BoQ item.",
            icon="INFO",
        )

    def execute(self, context):
        from bonsai import tool
        import bonsai.bim.module.cost.data

        lookup = {
            (m["boq_item"].Identification or "", m["boq_item"].Name or ""): m
            for m in _state["mismatched"]
        }

        modified = 0
        for (identification, rate_name), resolution in _state["resolutions"].items():
            if resolution == "SKIP":
                continue
            m = lookup.get((identification, rate_name))
            if not m:
                continue

            boq_item, sor_item = m["boq_item"], m["sor_item"]
            source, target = (boq_item, sor_item) if resolution == "BOQ_TO_SOR" else (sor_item, boq_item)

            item_attrs = {}
            for d in m["diffs"]:
                if d["field"] == "Name":
                    item_attrs["Name"] = source.Name or ""
                elif d["field"] == "Description":
                    item_attrs["Description"] = source.Description or ""
            if item_attrs:
                tool.Ifc.run("cost.edit_cost_item", cost_item=target, attributes=item_attrs)

            if any(d["field"] == "Value" for d in m["diffs"]):
                _replace_cost_values(tool, source, target)

            modified += 1

        if modified:
            bonsai.bim.module.cost.data.refresh()
            tool.Cost.load_cost_schedule_tree()

        self.report({"INFO"}, f"Resolved {modified} rate(s).")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------

class BoQToSoRPanel(bpy.types.Panel):
    bl_label = "BoQ to Schedule of Rates"
    bl_idname = "SCENE_PT_boq_to_schedule_of_rates"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Rate List"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        try:
            props = context.scene.BIMCostProperties
            if props.active_cost_schedule_id != 0:
                from bonsai import tool
                schedule = tool.Ifc.get().by_id(int(props.active_cost_schedule_id))
                if schedule.PredefinedType not in VALID_TYPES:
                    layout.label(text="Active schedule is not a Bill of Quantities.", icon="INFO")
                    return
        except Exception:
            layout.label(text="No IFC file loaded.", icon="INFO")
            return

        layout.prop(context.scene, "boq_to_sor_mode", expand=True)

        if context.scene.boq_to_sor_mode == "UPDATE":
            layout.prop(context.scene, "boq_to_sor_target_schedule", text="Target SoR")

        layout.operator(BoQToSoROperator.bl_idname, icon="LINENUMBERS_ON")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = [
    MismatchedRateResolution,
    BoQToSoROperator,
    BoQToSoRItemInfoOperator,
    BoQToSoRCopyReportOperator,
    COST_UL_MismatchedRates,
    BoQToSoRSetResolutionOperator,
    BoQToSoRResolveOperator,
    BoQToSoRPanel,
]

class_register, class_unregister = bpy.utils.register_classes_factory(classes)


def register():
    class_register()
    bpy.types.Scene.boq_to_sor_mode = bpy.props.EnumProperty(
        name="Mode",
        items=[
            ("NEW", "Create New", "Create a new Schedule of Rates"),
            ("UPDATE", "Update Existing", "Add missing items to an existing Schedule of Rates"),
        ],
        default="NEW",
    )
    bpy.types.Scene.boq_to_sor_target_schedule = bpy.props.EnumProperty(
        name="Schedule of Rates",
        items=_sor_schedule_items,
    )
    bpy.types.Scene.boq_to_sor_mismatched_rates = bpy.props.CollectionProperty(
        type=MismatchedRateResolution,
    )
    bpy.types.Scene.boq_to_sor_mismatched_index = bpy.props.IntProperty(default=0)


def unregister():
    del bpy.types.Scene.boq_to_sor_mode
    del bpy.types.Scene.boq_to_sor_target_schedule
    del bpy.types.Scene.boq_to_sor_mismatched_rates
    del bpy.types.Scene.boq_to_sor_mismatched_index
    class_unregister()


register()
