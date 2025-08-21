from typing import Union, List, TypedDict

import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator

import textwrap
import json


class XmlRateItem(TypedDict):
    index: int
    level: int
    is_parent: bool
    parents: str
    id: str
    name: str
    desc: str
    unit: str
    value: float
    labor: float
    safety: float


class XMLParser:
    title: str
    desc: str
    year: str
    xml_rate_list: List[XmlRateItem]

    def __init__(self):
        self.xml_rate_list = []

    def parse_header(self, root):
        # module to be implemented by each importer classes
        pass

    def parse_items(self, root):
        # module to be implemented by each importer classes
        pass

    def get_root(self, filename):
        import xml.etree.ElementTree as ET

        tree = ET.parse(filename)
        return tree.getroot()

    def clean_text(self, text: str):
        import re

        return re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)


class ParserXmlVeneto(XMLParser):
    def parse(self, root):
        index = 0
        settori = root.findall("settore")
        for settore in settori:
            self.xml_rate_list.append(
                {
                    "index": index,
                    "level": 0,
                    "is_parent": True,
                    "parents": "",
                    "id": settore.attrib["cod"],
                    "name": settore.attrib["desc"],
                    "desc": "",
                    "unit": "",
                    "value": 0.0,
                    "labor": 0.0,
                    "safety": 0.0,
                }
            )
            n_settore = index
            index += 1
            for capitolo in settore:
                self.xml_rate_list.append(
                    {
                        "index": index,
                        "level": 1,
                        "is_parent": True,
                        "parents": str(n_settore),
                        "id": capitolo.attrib["cod"],
                        "name": capitolo.attrib["desc"],
                        "desc": "",
                        "unit": "",
                        "value": 0.0,
                        "labor": 0.0,
                        "safety": 0.0,
                    }
                )
                n_capitolo = index
                index += 1
                for paragrafo in capitolo:
                    self.xml_rate_list.append(
                        {
                            "index": index,
                            "level": 2,
                            "is_parent": True,
                            "parents": str(n_settore) + "," + str(n_capitolo),
                            "id": paragrafo.attrib["cod"],
                            "name": paragrafo[0].text,
                            "desc": paragrafo[1].text,
                            "unit": "",
                            "value": 0.0,
                            "labor": 0.0,
                            "safety": 0.0,
                        }
                    )
                    prezzi = paragrafo.findall(".//prezzo")
                    n_paragrafo = index
                    index += 1
                    for prezzo in prezzi:
                        self.xml_rate_list.append(
                            {
                                "index": index,
                                "level": 3,
                                "is_parent": False,
                                "parents": str(n_settore)
                                + ","
                                + str(n_capitolo)
                                + ","
                                + str(n_paragrafo),
                                "id": prezzo.attrib["cod"],
                                "name": prezzo.text,
                                "desc": paragrafo[1].text,
                                "unit": prezzo.attrib["umi"],
                                "value": float(prezzo.attrib["val"]),
                                "labor": float(prezzo.attrib["man"])
                                * float(prezzo.attrib["val"])
                                / 100
                                or 0.0,
                                "safety": 0.0,
                            }
                        )
                        index += 1


class ParserXmlBasilicata(XMLParser):
    def parse(self, root):
        # TODO: implement custom parser
        return None


class ParserXmlToscana(XMLParser):
    def parse(self, root):
        # TODO: implement custom parser
        return None


class ParserXmlLiguria(XMLParser):
    def parse(self, root):
        # TODO: implement custom parser
        return None


class ParserXmlLombardia(XMLParser):
    def parse(self, root):
        # TODO: implement custom parser
        return None


class ParserXmlSardegna(XMLParser):
    def parse(self, root):
        # TODO: implement custom parser
        return None


class ParserXmlSix(XMLParser):
    def parse(self, root):
        # TODO: implement custom parser
        return None


class ImportXMLRateList(Operator, ImportHelper):
    """This appears in the tooltip of the operator and in the generated docs"""

    bl_idname = "import.xml_rate_list_import"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Import XML Rate List"
    filename_ext = ".xml"
    filter_glob: bpy.props.StringProperty(
        default="*.xml",
        options={"HIDDEN"},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )
    use_setting: bpy.props.BoolProperty(
        name="Example Boolean",
        description="Example Tooltip",
        default=True,
    )

    def execute(self, context):
        parser = ParserXmlVeneto()
        root = parser.get_root(self.filepath)
        parser.parse(root)

        context.scene.xml_rate_list.clear()
        for rate in parser.xml_rate_list:
            item = context.scene.xml_rate_list.add()
            item.name = rate["id"] + " - " + rate["name"]
            item.level = rate["level"]
            item.is_parent = rate["is_parent"]
            item.parents = rate["parents"]
            item.attributes = json.dumps(rate)

        return {"FINISHED"}


def create_cost_item(file, selected_rate, create_new_item=True):
    import ifcopenshell
    import bonsai

    active_ui_cost_item = bpy.context.scene.BIMCostProperties.active_cost_item
    active_ifc_cost_item = file.by_id(active_ui_cost_item.ifc_definition_id)

    # TODO: Remove previous cost values or edit them while updating

    if create_new_item:
        if active_ifc_cost_item in ifcopenshell.util.cost.get_root_cost_items(
            file.by_id(bpy.context.scene.BIMCostProperties.active_cost_schedule_id)
        ):
            cost_item = ifcopenshell.api.cost.add_cost_item(
                file, cost_item=active_ifc_cost_item
            )
        elif active_ui_cost_item.has_children:
            cost_item = ifcopenshell.api.cost.add_cost_item(
                file, cost_item=active_ifc_cost_item
            )
        else:
            cost_item = ifcopenshell.api.cost.add_cost_item(
                file, cost_item=active_ifc_cost_item.Nests[0].RelatingObject
            )
    else:
        cost_item = active_ifc_cost_item

    rate_attrib = json.loads(selected_rate.attributes)
    cost_item.Identification = rate_attrib["id"]
    cost_item.Name = rate_attrib["name"]
    cost_item.Description = rate_attrib["desc"]
    cost_value = ifcopenshell.api.cost.add_cost_value(file, parent=cost_item)

    ifcopenshell.api.cost.edit_cost_value(
        file, cost_value, attributes={"AppliedValue": rate_attrib["value"]}
    )

    if float(rate_attrib["labor"]) != 0.0:
        cost_value.ArithmeticOperator = "ADD"
        sub_cost_value_1 = ifcopenshell.api.cost.add_cost_value(file, parent=cost_value)
        sub_cost_value_2 = ifcopenshell.api.cost.add_cost_value(file, parent=cost_value)
        ifcopenshell.api.cost.edit_cost_value(
            file,
            sub_cost_value_1,
            attributes={"AppliedValue": rate_attrib["value"] - rate_attrib["labor"]},
        )
        ifcopenshell.api.cost.edit_cost_value(
            file,
            sub_cost_value_2,
            attributes={"Category": "Labor", "AppliedValue": rate_attrib["labor"]},
        )

    bonsai.bim.module.cost.data.refresh()
    bonsai.tool.Cost.load_cost_schedule_tree()


class UpdateActiveCostItem(bpy.types.Operator):
    """Update active cost item with selected rate data."""

    bl_idname = "import.xml_rate_update_cost_item"
    bl_label = "Update active cost item"

    @classmethod
    def poll(self, context):
        return False

    def execute(
        self, context
    ):  # TODO: Remove previous cost values or edit them while updating
        from bonsai import tool

        xml_rate_list_selected_item = bpy.context.scene.xml_rate_list[
            bpy.context.scene.xml_rate_list_active_index
        ]
        file = tool.Ifc.get()
        create_cost_item(
            file, selected_rate=xml_rate_list_selected_item, create_new_item=False
        )
        return {"FINISHED"}


class ImportRateToActiveCostSchedule(bpy.types.Operator):
    """Add a new cost item to the active schedule with selected rate data."""

    bl_idname = "import.xml_rate_add_cost_item"
    bl_label = "Import Rate to Active Cost Schedule"

    @classmethod
    def poll(self, context):
        try:
            if (
                len(getattr(bpy.context.scene, "xml_rate_list", [])) > 0
                and bpy.context.scene.BIMCostProperties.active_cost_item != None
            ):
                return True
            else:
                return False
        except:
            return False

    def execute(self, context):
        from bonsai import tool

        selected_rate = bpy.context.scene.xml_rate_list[
            bpy.context.scene.xml_rate_list_active_index
        ]
        file = tool.Ifc.get()
        create_cost_item(file, selected_rate=selected_rate, create_new_item=True)
        return {"FINISHED"}


class XmlRateCustomUIList(bpy.types.UIList):
    def draw_filter(self, context, layout):
        # Only show search box, no other filter options
        layout.prop(self, "filter_name", text="", icon="VIEWZOOM")

    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        # Add indentation based on level
        rate_attrib = json.loads(item.attributes)
        layout.alignment = "LEFT"
        if rate_attrib["is_parent"]:
            # Parent with expand/collapse
            icon_expand = "DOWNARROW_HLT" if item.is_expanded else "RIGHTARROW"
            row = layout.row()
            row.alignment = "RIGHT"
            if item.level != 0:
                row.label(text="  " * item.level)
            op = row.operator("custom.toggle", text="", icon=icon_expand, emboss=False)
            row.label(text=item.name)
            op.index = index
        else:
            # Child item
            layout.label(text="                       " + item.name)

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        flt_flags = []
        flt_neworder = []

        # Get search filter from UIList
        if self.filter_name:
            # Use Blender's built-in search functionality
            flt_flags = bpy.types.UI_UL_list.filter_items_by_name(
                self.filter_name,
                self.bitflag_filter_item,
                items,
                "name",
                reverse=self.use_filter_sort_reverse,
            )
            # make sure hierarchy is shown during item search
            search_filtered_flags = flt_flags[:]
            for i, item in enumerate(items):
                if flt_flags[i] & self.bitflag_filter_item:
                    current_parents_idx = item.parents.split(",")
                    for parent_idx in current_parents_idx:
                        search_filtered_flags[int(parent_idx)] = (
                            self.bitflag_filter_item
                        )
            flt_flags = search_filtered_flags

        else:
            hide_next = False
            hide_level = 10
            for item in items:
                show_item = True
                if hide_next:
                    if item.level <= hide_level:
                        show_item = True
                        if item.is_expanded:
                            hide_next = False
                        else:
                            hide_next = True
                            hide_level = item.level
                    else:
                        show_item = False
                else:
                    show_item = True
                    if item.is_expanded:
                        hide_next = False
                    else:
                        hide_next = True
                        hide_level = item.level

                flt_flags.append(self.bitflag_filter_item if show_item else 0)

        return flt_flags, flt_neworder


class CUSTOM_OT_toggle(Operator):
    bl_idname = "custom.toggle"
    bl_label = "Toggle"

    index: bpy.props.IntProperty()

    def execute(self, context):
        item = context.scene.xml_rate_list[self.index]
        item.is_expanded = not item.is_expanded
        return {"FINISHED"}


class CUSTOM_OT_collapse_to_level_0(Operator):
    bl_idname = "custom.collapse_to_level_0"
    bl_label = "Collapse to Level 0"

    def execute(self, context):
        items = context.scene.xml_rate_list
        for item in items:
            if item.is_parent:
                item.is_expanded = item.level < 0
        return {"FINISHED"}


class CUSTOM_OT_collapse_to_level_1(Operator):
    bl_idname = "custom.collapse_to_level_1"
    bl_label = "Collapse to Level 1"

    def execute(self, context):
        items = context.scene.xml_rate_list
        for item in items:
            if item.is_parent:
                item.is_expanded = item.level < 1
        return {"FINISHED"}


class CUSTOM_OT_expand_all(Operator):
    bl_idname = "custom.expand_all"
    bl_label = "Expand All"

    def execute(self, context):
        items = context.scene.xml_rate_list
        for item in items:
            if item.is_parent:
                item.is_expanded = True
        return {"FINISHED"}


class RateListPropGroup(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    level: bpy.props.IntProperty()
    is_parent: bpy.props.BoolProperty()
    parents: bpy.props.StringProperty()
    attributes: bpy.props.StringProperty()
    is_expanded: bpy.props.BoolProperty(default=True)


class RateListPanel(bpy.types.Panel):
    bl_label = "XML Rate List - Importer"
    bl_idname = "SCENE_PT_list_demo"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "XML Rate List"
    active_item_info = "no item selected"

    def get_active_item_info(self, context):
        return RateListPanel.active_item_info

    def rate_list_selection_callback(self, context):
        selected_rate = bpy.context.scene.xml_rate_list.items()[
            bpy.context.scene.xml_rate_list_active_index
        ][1]
        attrib = json.loads(selected_rate.attributes)
        new_label = ""
        new_label += attrib["id"]
        new_label += "\n"
        new_label += attrib["name"]
        new_label += "\n"
        new_label += str(attrib["unit"] or "-\n")
        new_label += "\n"
        new_label += str(attrib["value"] or "-\n")
        new_label += "\n"
        new_label += str(attrib["labor"] or "-\n")
        new_label += "\n"
        new_label += str(attrib["safety"] or "-\n")
        new_label += "\n"
        new_label += "Description:\n"
        description = textwrap.wrap(attrib["desc"], 100)
        for row in description:
            new_label += row + "\n"
        
        RateListPanel.active_item_info = new_label

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator(ImportXMLRateList.bl_idname, text="Import Rate List")
        layout.label(text="XML Rate List: {}".format("Not yet implemented"))
        row = layout.row()
        row.operator(CUSTOM_OT_collapse_to_level_0.bl_idname, text="Collapse")
        row.operator(CUSTOM_OT_collapse_to_level_1.bl_idname, text="To Level 1")
        row.operator(CUSTOM_OT_expand_all.bl_idname, text="Expand All")
        layout.template_list(
            "XmlRateCustomUIList",
            "",
            context.scene,
            "xml_rate_list",
            context.scene,
            "xml_rate_list_active_index",
            rows=8,
        )  # More rows for large lists
        box = layout.box()
        row = box.row()
        rate_info = self.get_active_item_info(context).split("\n")
        if len(rate_info)>4:
            row.label(text=rate_info[0])
            btn_row = row.row(align=True)
            btn_row.alignment = "RIGHT"
            btn_row.operator(ImportRateToActiveCostSchedule.bl_idname, text="", icon="ADD")
            btn_row.operator(UpdateActiveCostItem.bl_idname, text="", icon="FILE_REFRESH")

            
            row=box.row()
            box.label(text=rate_info[1])
            row=box.row()
            row.label(text="unit: "+rate_info[2])
            row.label(text="value: "+rate_info[3])
            row=box.row()
            row.label(text="labor: "+rate_info[4])
            row.label(text="safety: "+rate_info[5])
            for row in rate_info[6:]:
                layout.label(text=row)


classes = [
    XmlRateCustomUIList,
    CUSTOM_OT_toggle,
    CUSTOM_OT_collapse_to_level_0,
    CUSTOM_OT_collapse_to_level_1,
    CUSTOM_OT_expand_all,
    UpdateActiveCostItem,
    ImportRateToActiveCostSchedule,
    ImportXMLRateList,
    RateListPropGroup,
    RateListPanel,
]


class_register, class_unregister = bpy.utils.register_classes_factory(classes)


def register():
    class_register()
    bpy.types.Scene.xml_rate_list = bpy.props.CollectionProperty(type=RateListPropGroup)
    bpy.types.Scene.xml_rate_list_active_index = bpy.props.IntProperty(
        update=RateListPanel.rate_list_selection_callback
    )


def unregister():
    class_unregister()
    del bpy.types.Scene.xml_rate_list
    del bpy.types.Scene.xml_rate_list_active_index


register()
