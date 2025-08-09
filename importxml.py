import bpy
import os
import xml.etree.ElementTree as ET
import textwrap
import json
from bonsai import tool
import ifcopenshell

from bl_ui.generic_ui_list import draw_ui_list

from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

source = os.path.join( "c:\\120grammi Dropbox\\120grammi_risorse\\01-Prezzari", "Regione Veneto", "elencoPrezzi2025.xml")

def parse_xml_file(filename):
    tree = ET.parse(filename)
    root = tree.getroot()
    return tree, root


def get_xml_levels(element, level=0, levels=None):
    if levels is None:
        levels = {}
    if level not in levels:
        levels[level] = element.tag
    for child in element:
        get_xml_levels(child, level + 1, levels)
    return levels.values()


def read_xml_rate_list(filepath):
    tree, root = parse_xml_file(filepath)
    return root.findall(".//prezzo")


def update_xml_rate_list(context, filepath, use_some_setting):
    rate_list = read_xml_rate_list(filepath)

    context.scene.xml_rate_list.clear()
    for i in rate_list:
        item = context.scene.xml_rate_list.add()
        item.name = i.text
        item.attributes = json.dumps(i.attrib)
        
    return {'FINISHED'}



class ImportXMLRateList(Operator, ImportHelper):
    """This appears in the tooltip of the operator and in the generated docs"""
    bl_idname = "import_test.xml_rate_list_import"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Import Some Data"

    # ImportHelper mix-in class uses this.
    filename_ext = ".xml"

    filter_glob: StringProperty(
        default="*.xml",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )
    use_setting: BoolProperty(
        name="Example Boolean",
        description="Example Tooltip",
        default=True,
    )

    def execute(self, context):
        bpy.types.Scene.xml_rate_list_active_list_filepath = self.filepath
        update_xml_rate_list(context, self.filepath, self.use_setting)
        return {'FINISHED'}



class ImportRateToActiveCostSchedule(bpy.types.Operator):
    """Tooltip"""
    bl_idname = "object.simple_operator"
    bl_label = "Simple Object Operator"


    def execute(self, context):
        selected_rate = read_xml_rate_list(bpy.context.scene.xml_rate_list_active_list_filepath)[bpy.context.scene.xml_rate_list_active_index]
        print(selected_rate.text)
        file = tool.Ifc.get()
        #active_cost_schedule=file.by_id(bpy.context.scene.BIMCostProperties.active_cost_schedule_id)
        active_cost_schedule = file.by_type("IfcCostSchedule")[0]
        cost_item=ifcopenshell.api.cost.add_cost_item(file, cost_schedule=active_cost_schedule)
        cost_item.Description = selected_rate.text
        cost_item.Name = textwrap.shorten(text=selected_rate.text, width=30, placeholder="")
        cost_item.Identification = selected_rate.attrib["cod"]
        cost_value = ifcopenshell.api.cost.add_cost_value(file, parent=cost_item)
        cost_value.ArithmeticOperator="ADD"
        ifcopenshell.api.cost.edit_cost_value(file, cost_value,
        attributes={"AppliedValue": float(selected_rate.attrib["val"])})
        sub_cost_value_1 = ifcopenshell.api.cost.add_cost_value(file, parent=cost_value)
        sub_cost_value_2 = ifcopenshell.api.cost.add_cost_value(file, parent=cost_value)
        ifcopenshell.api.cost.edit_cost_value(file, sub_cost_value_1,
        attributes={"AppliedValue": float(selected_rate.attrib["val"])*(1-float(selected_rate.attrib["man"])/100)})
        ifcopenshell.api.cost.edit_cost_value(file, sub_cost_value_2,
        attributes={"Category": "Labor", "AppliedValue": float(selected_rate.attrib["val"])*float(selected_rate.attrib["man"])/100})
        #tool.Cost.load_cost_schedule_tree()v

        return {'FINISHED'}


class RateListPropGroup(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    attributes:  bpy.props.StringProperty()


            
class RateListPanel(bpy.types.Panel):
    bl_label = "XML Rate List - Importer"
    bl_idname = "SCENE_PT_list_demo"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "XML Rate List"
    
    active_item_info = "no item selected"
    
    def get_active_item_info(self, context):
        return RateListPanel.active_item_info

    def rate_list_selection_callback(self, context):
        selected_rate = bpy.context.scene.xml_rate_list.items()[bpy.context.scene.xml_rate_list_active_index][1]
        print
        new_label=""
        description = textwrap.wrap(selected_rate.name)
        for row in description:
            new_label += row + "\n"
        attrib=json.loads(selected_rate.attributes)
        for key in attrib:
            new_label += "\n" 
            new_label += key 
            new_label += ": "
            new_label += attrib[key]
        RateListPanel.active_item_info = new_label

    def draw(self, context):
        layout = self.layout
        layout.operator(ImportXMLRateList.bl_idname, text="Import Rate List")
        layout.label(text="XML Rate List: {}".format("Not yet implemented"))
        draw_ui_list(
            layout,
            context,
            list_path="scene.xml_rate_list",
            active_index_path="scene.xml_rate_list_active_index",
            unique_id="xml_rate_list_id",
        )
        for row in self.get_active_item_info(context).split('\n'):
            layout.label(text=row)
        layout.operator(ImportRateToActiveCostSchedule.bl_idname, text="Import Rate to Active Cost Schedule")
        


classes = [
    ImportRateToActiveCostSchedule,
    ImportXMLRateList,
    RateListPropGroup,
    RateListPanel,
]

class_register, class_unregister = bpy.utils.register_classes_factory(classes)


def register():
    class_register()
    bpy.types.Scene.xml_rate_list = bpy.props.CollectionProperty(type=RateListPropGroup)
    bpy.types.Scene.xml_rate_list_active_index = bpy.props.IntProperty(update=RateListPanel.rate_list_selection_callback)
    bpy.types.Scene.xml_rate_list_active_list_filepath = bpy.props.StringProperty()


def unregister():
    class_unregister()
    del bpy.types.Scene.xml_rate_list
    del bpy.types.Scene.xml_rate_list_active_index
    del bpy.types.Scene.xml_rate_list_active_list_filepath


register()
