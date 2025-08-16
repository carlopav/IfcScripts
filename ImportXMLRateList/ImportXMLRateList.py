import bpy
from bl_ui.generic_ui_list import draw_ui_list
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

import os
import textwrap
import json


source = os.path.join( "c:\\120grammi Dropbox\\120grammi_risorse\\01-Prezzari", "Regione Veneto", "elencoPrezzi2025.xml")

#------------------------------------------------------ HELPER FUNCTIONS

'''import LeenoImport_XmlSix
import LeenoImport_XmlToscana
import LeenoImport_XmlSardegna
import LeenoImport_XmlLiguria
import LeenoImport_XmlVeneto
import LeenoImport_XmlBasilicata
import LeenoImport_XmlLombardia'''


def fixParagraphSize(txt):
    '''
    corregge il paragrafo della descrizione negli elenchi prezzi
    in modo che LibreOffice calcoli correttamente l'altezza della cella
    '''
    minLen = 130
    splitted = txt.split('\n')
    if len(splitted) > 1:
        spl0 = splitted[0]
        spl1 = splitted[1]
        if len(spl0) + len(spl1) < minLen:
            dl = minLen - len(spl0) - len(spl1)
            spl0 = spl0 + dl * " "
            txt = spl0 + '\n' + spl1
            for t in splitted[2:]:
                txt += '\n' + t
    return txt


def stripXMLNamespaces(data):
    '''
    prende una stringa contenente un file XML
    elimina i namespaces dai dati
    e ritorna il root dell' XML
    '''
    it = ET.iterparse(StringIO(data))
    for _, el in it:
        # strip namespaces
        _, _, el.tag = el.tag.rpartition('}')
    return it.root


def findXmlParser(xmlText):
    '''
    fa un pre-esame del contenuto xml della stringa fornita
    per determinare se si tratta di un tipo noto
    (nel qual caso fornisce un parser adatto) oppure no
    (nel qual caso avvisa di inviare il file allo staff)
    '''

    parsers = {
        'xmlns="six.xsd"': LeenoImport_XmlSix.parseXML,
        'autore="Regione Toscana"': LeenoImport_XmlToscana.parseXML,
        'autore="Regione Calabria"': LeenoImport_XmlToscana.parseXML,
        'autore="Regione Campania"': LeenoImport_XmlToscana.parseXML,
        'autore="Regione Sardegna"': LeenoImport_XmlSardegna.parseXML,
        'autore="Regione Liguria"': LeenoImport_XmlLiguria.parseXML,
        'rks=': LeenoImport_XmlVeneto.parseXML,
        '<pdf>Prezzario_Regione_Basilicata': LeenoImport_XmlBasilicata.parseXML,
        '<autore>Regione Lombardia': LeenoImport_XmlLombardia.parseXML,
        '<autore>LOM': LeenoImport_XmlLombardia.parseXML,
        'xsi:noNamespaceSchemaLocation="Parte': LeenoImport_XmlLombardia.parseXML1,
    }

    # controlla se il file è di tipo conosciuto...
    for pattern, xmlParser in parsers.items():
        if pattern in xmlText:
            # si, ritorna il parser corrispondente
            return xmlParser

    # non trovato... ritorna None
    return None

#------------------------------------------------------


def parse_xml_file(filename):
    import xml.etree.ElementTree as ET
    tree = ET.parse(filename)
    root = tree.getroot()
    return tree, root


def read_xml_rate_list(filepath):
    tree, root = parse_xml_file(filepath)
    xml_tree_list = []
    settori = root.findall("settore")
    for settore in settori:
        xml_tree_list.append((settore.attrib["cod"]+" - "+settore.attrib["desc"],"",0,settore.attrib))
        for capitolo in settore:
            xml_tree_list.append((capitolo.attrib["cod"]+" - "+capitolo.attrib["desc"],"",1,capitolo.attrib))
            for paragrafo in capitolo:
                xml_tree_list.append((paragrafo.attrib["cod"]+" - "+paragrafo[0].text,paragrafo[1].text, 2, paragrafo.attrib))
                prezzi=paragrafo.findall(".//prezzo")
                for prezzo in prezzi:
                    xml_tree_list.append((prezzo.attrib["cod"]+" - "+prezzo.text,"", 3, prezzo.attrib))
                    
    return xml_tree_list


def update_xml_rate_list(context, filepath, use_some_setting):
    rate_list = read_xml_rate_list(filepath)
    context.scene.xml_rate_list.clear()
    for i in rate_list:
        item = context.scene.xml_rate_list.add()
        item.name = "      "*i[2]+i[0]
        item.description = i[1]
        item.attributes = json.dumps(i[3])
    return {'FINISHED'}


class ImportXMLRateList(Operator, ImportHelper):
    """This appears in the tooltip of the operator and in the generated docs"""
    bl_idname = "import.xml_rate_list_import"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Import Some Data"
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
    
    cost_item.Name = selected_rate[0].split(" - ")[1]
    cost_item.Description = selected_rate[1]
    attributes = selected_rate[3]
    cost_item.Identification = attributes["cod"]
    cost_value = ifcopenshell.api.cost.add_cost_value(file, parent=cost_item)
    cost_value.ArithmeticOperator="ADD"
    ifcopenshell.api.cost.edit_cost_value(file, cost_value,
    attributes={"AppliedValue": float(attributes["val"])})
    
    if float(attributes["man"]) != 0.0:
        sub_cost_value_1 = ifcopenshell.api.cost.add_cost_value(file, parent=cost_value)
        sub_cost_value_2 = ifcopenshell.api.cost.add_cost_value(file, parent=cost_value)
        ifcopenshell.api.cost.edit_cost_value(file, sub_cost_value_1,
        attributes={"AppliedValue": float(attributes["val"])*(1-float(attributes["man"])/100)})
        ifcopenshell.api.cost.edit_cost_value(file, sub_cost_value_2,
        attributes={"Category": "Labor", "AppliedValue": float(attributes["val"])*float(attributes["man"])/100})
    
    bonsai.bim.module.cost.data.refresh()
    bonsai.tool.Cost.load_cost_schedule_tree()


class UpdateActiveCostItem(bpy.types.Operator):
    """Update active cost item with selected rate data."""
    bl_idname = "object.simple_operator"
    bl_label = "Import Rate to Active Cost Schedule"
    
    @classmethod
    def poll(self, context):
        try:
            bpy.context.scene.xml_rate_list_active_list_filepath
            bpy.context.scene.xml_rate_list
            bpy.context.scene.xml_rate_list_active_index
            return True
        except:
            return False

    def execute(self, context):
        from bonsai import tool
        #TODO: load informations right from the list element without reading the file again
        selected_rate = read_xml_rate_list(bpy.context.scene.xml_rate_list_active_list_filepath)[bpy.context.scene.xml_rate_list_active_index]
        file = tool.Ifc.get()
        
        create_cost_item(file, selected_rate=selected_rate, create_new_item=False)

        return {'FINISHED'}


class ImportRateToActiveCostSchedule(bpy.types.Operator):
    """Add a new cost item to the active schedule with selected rate data."""
    bl_idname = "object.simple_operator"
    bl_label = "Import Rate to Active Cost Schedule"
    
    @classmethod
    def poll(self, context):
        try:
            bpy.context.scene.xml_rate_list_active_list_filepath
            bpy.context.scene.xml_rate_list
            bpy.context.scene.xml_rate_list_active_index
            return True
        except:
            return False

    def execute(self, context):
        from bonsai import tool
        #TODO: load informations right from the list element without reading the file again
        selected_rate = read_xml_rate_list(bpy.context.scene.xml_rate_list_active_list_filepath)[bpy.context.scene.xml_rate_list_active_index]
        file = tool.Ifc.get()
        
        create_cost_item(file, selected_rate=selected_rate, create_new_item=True)

        return {'FINISHED'}


class RateListPropGroup(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    description: bpy.props.StringProperty()
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
        new_label += attrib["cod"]
        new_label += "\n"
        name = textwrap.wrap(selected_rate.name.split(" - ")[1], 100)
        for row in name:
            new_label += row + "\n"
        new_label += "                                                        -----\n"
        description = textwrap.wrap(selected_rate.description, 100)
        for row in description:
            new_label += row + "\n"
        new_label += "                                                        -----\n"
        
        for key in attrib:
            new_label += "\n" 
            new_label += key 
            new_label += ": "
            new_label += attrib[key]
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
        btn_row.operator(ImportRateToActiveCostSchedule.bl_idname, text="", icon='FILE_REFRESH')

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
    bpy.types.Scene.xml_rate_list_active_list_filepath = bpy.props.StringProperty()


def unregister():
    class_unregister()
    del bpy.types.Scene.xml_rate_list
    del bpy.types.Scene.xml_rate_list_active_index
    del bpy.types.Scene.xml_rate_list_active_list_filepath


register()