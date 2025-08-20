from typing import Union, List, TypedDict

import bpy
from bl_ui.generic_ui_list import draw_ui_list
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

import sys
import os
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
        security: float


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
    
    def clean_text(self, text:str):
        import re
        return re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)


class ParserXmlVeneto(XMLParser):
    def parse(self, root):
        index = 0
        settori = root.findall("settore")
        for settore in settori:
            self.xml_rate_list.append({ "index": index,
                                        "level": 0,
                                        "is_parent": True,
                                        "parents": "",
                                        "id": settore.attrib["cod"],
                                        "name": settore.attrib["desc"],
                                        "desc": "",
                                        "unit": "",
                                        "value": 0.0,
                                        "labor": 0.0,
                                        "security": 0.0
                                        })
            n_settore = index
            index += 1
            for capitolo in settore:
                self.xml_rate_list.append({ "index": index,
                                            "level": 1,
                                            "is_parent": True,
                                            "parents": str(n_settore),
                                            "id": capitolo.attrib["cod"],
                                            "name": capitolo.attrib["desc"],
                                            "desc": "",
                                            "unit": "",
                                            "value": 0.0,
                                            "labor": 0.0,
                                            "security": 0.0
                                            })
                n_capitolo = index
                index += 1
                for paragrafo in capitolo:
                    self.xml_rate_list.append({ "index": index,
                                                "level": 2,
                                                "is_parent": True,
                                                "parents": str(n_settore)+","+str(n_capitolo),
                                                "id": paragrafo.attrib["cod"],
                                                "name": paragrafo[0].text,
                                                "desc": paragrafo[1].text,
                                                "unit": "",
                                                "value": 0.0,
                                                "labor": 0.0,
                                                "security": 0.0
                                                })
                    prezzi=paragrafo.findall(".//prezzo")
                    n_paragrafo = index
                    index += 1
                    for prezzo in prezzi:
                        self.xml_rate_list.append({ "index": index,
                                                    "level": 3,
                                                    "is_parent": False,
                                                    "parents": str(n_settore)+","+str(n_capitolo)+","+str(n_paragrafo),
                                                    "id": prezzo.attrib["cod"],
                                                    "name": prezzo.text,
                                                    "desc": paragrafo[1].text,
                                                    "unit": prezzo.attrib["umi"],
                                                    "value": float(prezzo.attrib["val"]),
                                                    "labor": float(prezzo.attrib["man"])*float(prezzo.attrib["val"])/100 or 0.0,
                                                    "security": 0.0,
                                                    })
                        index += 1
                        

class ParserXmlBasilicata(XMLParser):
    def parse(self, root):
        #TODO: implement custom parser
        return None


class ParserXmlToscana(XMLParser):
    def parse(self, root):
        #TODO: implement custom parser
        return None


class ParserXmlLiguria(XMLParser):
    def parse(self, root):
        #TODO: implement custom parser
        return None


class ParserXmlLombardia(XMLParser):
    def parse(self, root):
        #TODO: implement custom parser
        return None


class ParserXmlSardegna(XMLParser):
    def parse(self, root):
        #TODO: implement custom parser
        return None


class ParserXmlSix(XMLParser):
    def parse(self, root):
        #TODO: implement custom parser
        return None


class ImportXMLRateList(Operator, ImportHelper):
    """This appears in the tooltip of the operator and in the generated docs"""
    bl_idname = "import.xml_rate_list_import"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Import XML Rate List"
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
        parser = ParserXmlVeneto()
        root = parser.get_root(self.filepath)
        parser.parse(root)
        
        context.scene.xml_rate_list.clear()
        for rate in parser.xml_rate_list:
            item = context.scene.xml_rate_list.add()
            item.name = "      "*rate["level"]+rate["name"]
            item.attributes = json.dumps(rate)
            
        return {'FINISHED'}


def create_cost_item(file, selected_rate, create_new_item=True):
    import ifcopenshell
    import bonsai
    active_ui_cost_item = bpy.context.scene.BIMCostProperties.active_cost_item
    active_ifc_cost_item=file.by_id(active_ui_cost_item.ifc_definition_id)
    
    if create_new_item:
        if active_ifc_cost_item in ifcopenshell.util.cost.get_root_cost_items(file.by_id(bpy.context.scene.BIMCostProperties.active_cost_schedule_id)):
            cost_item=ifcopenshell.api.cost.add_cost_item(file, cost_item=active_ifc_cost_item)
        elif active_ui_cost_item.has_children:
            cost_item=ifcopenshell.api.cost.add_cost_item(file, cost_item=active_ifc_cost_item)
        else:
            cost_item=ifcopenshell.api.cost.add_cost_item(file, cost_item=active_ifc_cost_item.Nests[0].RelatingObject)
    else:
        cost_item = active_ifc_cost_item
    
    rate_attrib = json.loads(selected_rate.attributes)
    cost_item.Identification = rate_attrib["id"]
    cost_item.Name = rate_attrib["name"]
    cost_item.Description = rate_attrib["desc"]
    cost_value = ifcopenshell.api.cost.add_cost_value(file, parent=cost_item)
    
    ifcopenshell.api.cost.edit_cost_value(file, cost_value,
    attributes={"AppliedValue": rate_attrib["value"]})
    
    if float(rate_attrib["labor"]) != 0.0:
        cost_value.ArithmeticOperator="ADD"
        sub_cost_value_1 = ifcopenshell.api.cost.add_cost_value(file, parent=cost_value)
        sub_cost_value_2 = ifcopenshell.api.cost.add_cost_value(file, parent=cost_value)
        ifcopenshell.api.cost.edit_cost_value(file, sub_cost_value_1,
        attributes={"AppliedValue": rate_attrib["value"]-rate_attrib["labor"]})
        ifcopenshell.api.cost.edit_cost_value(file, sub_cost_value_2,
        attributes={"Category": "Labor", "AppliedValue": rate_attrib["labor"]})
    
    bonsai.bim.module.cost.data.refresh()
    bonsai.tool.Cost.load_cost_schedule_tree()


class UpdateActiveCostItem(bpy.types.Operator):
    """Update active cost item with selected rate data."""
    bl_idname = "import.xml_rate_update_cost_item"
    bl_label = "Update active cost item"
    
    @classmethod
    def poll(self, context):
        try:
            if len(getattr(bpy.context.scene, "xml_rate_list", [])) > 0 and bpy.context.scene.BIMCostProperties.active_cost_item != None: 
                return True
            else:
                return False
        except:
            return False

    def execute(self, context):
        from bonsai import tool
        xml_rate_list_selected_item = bpy.context.scene.xml_rate_list[bpy.context.scene.xml_rate_list_active_index]
        file = tool.Ifc.get()
        create_cost_item(file, selected_rate=xml_rate_list_selected_item, create_new_item=False)
        return {'FINISHED'}


class ImportRateToActiveCostSchedule(bpy.types.Operator):
    """Add a new cost item to the active schedule with selected rate data."""
    bl_idname = "import.xml_rate_add_cost_item"
    bl_label = "Import Rate to Active Cost Schedule"
    
    @classmethod
    def poll(self, context):
        try:
            if len(getattr(bpy.context.scene, "xml_rate_list", [])) > 0 and bpy.context.scene.BIMCostProperties.active_cost_item != None: 
                return True
            else:
                return False
        except:
            return False

    def execute(self, context):
        from bonsai import tool
        selected_rate = bpy.context.scene.xml_rate_list[bpy.context.scene.xml_rate_list_active_index]
        file = tool.Ifc.get()
        create_cost_item(file, selected_rate=selected_rate, create_new_item=True)
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
        attrib=json.loads(selected_rate.attributes)
        new_label=""
        new_label += attrib["id"]
        new_label += "\n"
        name = textwrap.wrap(attrib["name"], 100)
        for row in name:
            new_label += row + "\n"
        new_label += "                                                        -----\n"
        description = textwrap.wrap(attrib["desc"], 100)
        for row in description:
            new_label += row + "\n"
        new_label += "                                                        -----\n"
        
        for key in attrib:
            new_label += "\n" 
            new_label += key 
            new_label += ": "
            new_label += str(attrib[key])
        RateListPanel.active_item_info = new_label

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator(ImportXMLRateList.bl_idname, text="Import Rate List")
        layout.label(text="XML Rate List: {}".format("Not yet implemented"))
        draw_ui_list(
            layout,
            context,
            list_path="scene.xml_rate_list",
            active_index_path="scene.xml_rate_list_active_index",
            unique_id="xml_rate_list_id",
        )
        row = layout.row()
        row.label(text=self.get_active_item_info(context).split('\n')[0])
        btn_row = row.row(align=True)
        btn_row.alignment = 'RIGHT'
        btn_row.operator(ImportRateToActiveCostSchedule.bl_idname, text="", icon='ADD')
        btn_row.operator(UpdateActiveCostItem.bl_idname, text="", icon='FILE_REFRESH')

        for row in self.get_active_item_info(context).split('\n')[1:]:
            layout.label(text=row)
        

classes = [
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
    bpy.types.Scene.xml_rate_list_active_index = bpy.props.IntProperty(update=RateListPanel.rate_list_selection_callback)
    

def unregister():
    class_unregister()
    del bpy.types.Scene.xml_rate_list
    del bpy.types.Scene.xml_rate_list_active_index


register()