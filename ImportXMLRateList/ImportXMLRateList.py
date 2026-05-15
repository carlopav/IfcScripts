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
    equipment: float
    materials: float
    safety: float


class XMLParser:
    title: str
    desc: str
    year: str
    language: []
    xml_rate_list: List[XmlRateItem]

    def __init__(self):
        self.xml_rate_list = []

    @staticmethod
    def get_xml_content(filename):
        with open(filename, "r", errors="ignore", encoding="utf8") as file:
            data = file.read()
        return data

    def parse_header(self, root):
        # module to be implemented by each importer classes
        pass

    def parse_items(self, xml_content):
        # module to be implemented by each importer classes
        pass

    def clean_xml_content(self, data):
        import re

        # clean non printable characters
        return re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", data)

    def get_stripped_xml_namespaces_root(self, data):
        import xml.etree.ElementTree as ET
        from io import StringIO

        it = ET.iterparse(StringIO(data))
        for _, el in it:
            if isinstance(el.tag, str) and "}" in el.tag:
                el.tag = el.tag.rpartition("}")[-1]
        return it.root

    def get_root(self, data):
        import xml.etree.ElementTree as ET
        from io import StringIO

        tree = ET.parse(StringIO(data))
        return tree.getroot()

    def clean_string(self, text):
        # sistema_cose (da Leeno)
        text = text.replace("\t", " ").replace("Ã¨", "è").replace("", "")
        text = text.replace("Â°", "°").replace("Ã", "à").replace(" $", "")
        text = text.replace("Ó", "à").replace("Þ", "é").replace("&#x13;", "")
        text = text.replace("&#xD;&#xA;", "").replace("&#xA;", "")
        text = text.replace("&apos;", "'").replace("&#x3;&#x1;", "")
        text = text.replace("\n \n", "\n")
        while "  " in text:
            text = text.replace("  ", " ")
        while "\n\n" in text:
            text = text.replace("\n\n", "\n")
        return text.strip()


class ParserXmlVeneto(XMLParser):
    def parse_items(self, xml_content):
        xml_content = self.clean_xml_content(xml_content)
        root = self.get_stripped_xml_namespaces_root(xml_content)
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
                    "equipment": 0.0,
                    "materials": 0.0,
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
                        "equipment": 0.0,
                        "materials": 0.0,
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
                            "equipment": 0.0,
                            "materials": 0.0,
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
                                "equipment": 0.0,
                                "materials": 0.0,
                                "safety": 0.0,
                            }
                        )
                        index += 1


class ParserXmlBasilicata(XMLParser):
    def parse_items(self, xml_content):
        # TODO: implement custom parser
        return None


class ParserXmlToscana(XMLParser):
    def parse_items(self, xml_content):
        # TODO: implement custom parser
        return None


class ParserXmlLiguria(XMLParser):
    def parse_items(self, xml_content):
        # TODO: implement custom parser
        return None


class ParserXmlLombardia(XMLParser):
    def parse_items(self, xml_content):
        # TODO: implement custom parser
        return None


class ParserXmlSardegna(XMLParser):
    def parse_items(self, xml_content):
        # TODO: implement custom parser
        return None


class ParserXmlSix(XMLParser):
    """Parser per formato XML SIX."""

    def __init__(self, language=None):
        super().__init__()
        self.language = language
        self.default_list_id = None

    def parse_items(self, xml_content):
        xml_content = self.clean_xml_content(xml_content)
        root = self.get_stripped_xml_namespaces_root(xml_content)
        prezzario = root.find("prezzario")
        if prezzario is None:
            return

        self.default_list_id = self._get_default_quotazione_id(prezzario)
        units = self.get_units(prezzario)
        products = prezzario.findall("prodotto")

        index = 0
        parents_prdId_indexes = {}

        for product in products:
            level = self.get_level_from_prdId(product)
            is_parent = level == 0 or self.is_parent(product)

            if is_parent:
                parents_prdId_indexes[product.attrib["prdId"]] = str(index)

            parents = ""
            parts = product.attrib["prdId"].split(".")
            parents_prdId = [".".join(parts[:i]) for i in range(len(parts) - 1, 0, -1)]
            for prdId in parents_prdId:
                if prdId in parents_prdId_indexes:
                    parents += parents_prdId_indexes[prdId] + ","
            parents = parents.strip(",")

            desc = product.find("prdDescrizione")
            name = self.clean_string(desc.attrib.get("breve", "")) if desc is not None else ""
            description = self.clean_string(desc.attrib.get("estesa", "")) if desc is not None else ""
            cost_value = self.get_value(product)

            self.xml_rate_list.append({
                "index": index,
                "level": level,
                "is_parent": is_parent,
                "parents": parents,
                "id": product.attrib.get("prdId", ""),
                "name": name,
                "desc": description,
                "unit": self.get_unit(units, product),
                "value": cost_value,
                "labor": self.get_value_component(product, cost_value, "incidenzaManodopera"),
                "equipment": self.get_value_component(product, cost_value, "incidenzaAttrezzatura"),
                "materials": self.get_value_component(product, cost_value, "incidenzaMateriali"),
                "safety": self.get_value_component(product, cost_value, "safety"),
            })
            index += 1

    def _get_default_quotazione_id(self, prezzario):
        lista = prezzario.find("listaQuotazione")
        if lista is not None:
            return lista.attrib.get("listaQuotazioneId")
        return None

    @staticmethod
    def get_units(prezzario):
        units = {}
        umList = prezzario.findall("unitaDiMisura")
        for um in umList:
            attr = um.attrib
            try:
                sym = attr.get("simbolo", attr.get("udmId", ""))
                units[attr["unitaDiMisuraId"]] = sym
            except KeyError:
                pass
        return units

    @staticmethod
    def get_unit(units, product):
        try:
            return units.get(product.attrib.get("unitaDiMisuraId", ""), "")
        except Exception:
            return ""

    def get_value(self, product):
        prezzo = 0.0
        quotazioni = product.findall("prdQuotazione")
        if not quotazioni:
            return 0.0

        for el in quotazioni:
            if self.default_list_id and el.attrib.get("listaQuotazioneId") == self.default_list_id:
                try:
                    return float(el.attrib.get("valore", 0.0))
                except ValueError:
                    return 0.0

        try:
            return float(quotazioni[0].attrib.get("valore", 0.0))
        except ValueError:
            return 0.0

    @staticmethod
    def get_value_component(product, cost_value, component_type):
        if component_type not in ("incidenzaManodopera", "incidenzaMateriali", "incidenzaAttrezzatura", "safety"):
            return 0.0
        component_ratio = product.find(component_type)
        try:
            return float(getattr(component_ratio, "text", 0.0)) * cost_value / 100
        except Exception:
            return 0.0

    @staticmethod
    def get_level_from_prdId(product):
        return len(product.attrib.get("prdId", "").split(".")) - 1

    @staticmethod
    def is_parent(product):
        return len(product.findall("prdQuotazione")) == 0


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
    chosen_parser: bpy.props.EnumProperty(
        name="Parser",
        description="Choose the available parser",
        items=[
            (
                "Auto",
                "Auto",
                "Try to guess which importer is more suitable for the given data",
            ),
            ("RegioneVeneto", "Regione Veneto", "Tooltip"),
            ("RegioneFriuliVeneziaGiulia", "Regione Friuli Venezia Giulia", "Tooltip"),
        ],
        default="RegioneVeneto",
    )

    def draw(self, context):
        layout = self.layout
        # layout.prop(self, "chosen_parser")
        box = layout.box()
        box.label(text="Options:")
        box.label(text="")

    def findXmlParser(self, xmlText):
        """
        From Leeno, thanks to Giuserpe!
        fa un pre-esame del contenuto xml della stringa fornita
        per determinare se si tratta di un tipo noto
        (nel qual caso fornisce un parser adatto) oppure no
        (nel qual caso avvisa di inviare il file allo staff)
        """

        parsers = {
            'xmlns="six.xsd"': ParserXmlSix,
            'autore="Regione Toscana"': ParserXmlToscana,
            'autore="Regione Calabria"': ParserXmlToscana,
            'autore="Regione Campania"': ParserXmlToscana,
            'autore="Regione Sardegna"': ParserXmlSardegna,
            'autore="Regione Liguria"': ParserXmlLiguria,
            "rks=": ParserXmlVeneto,
            "<pdf>Prezzario_Regione_Basilicata": ParserXmlBasilicata,
            "<autore>Regione Lombardia": ParserXmlLombardia,
            "<autore>LOM": ParserXmlLombardia,
            #'xsi:noNamespaceSchemaLocation="Parte': LeenoImport_XmlLombardia.parseXML1,
        }

        # controlla se il file è di tipo conosciuto...
        for pattern, xmlParser in parsers.items():
            if pattern in xmlText:
                # si, ritorna il parser corrispondente
                return xmlParser

        # non trovato... ritorna None
        return None

    def execute(self, context):
        xml_content = XMLParser.get_xml_content(self.filepath)
        parser = self.findXmlParser(xml_content)()
        if parser is None:
            self.report(
                {"ERROR"}, "Cannot automatically find a parser for selected file"
            )
            return {"CANCELLED"}
        # parser = available_parsers[self.chosen_parser]
        parser.parse_items(xml_content)

        context.scene.xml_rate_list.clear()
        for rate in parser.xml_rate_list:
            item = context.scene.xml_rate_list.add()
            item.name = rate["id"] + " - " + rate["name"]
            item.level = rate["level"]
            item.is_parent = rate["is_parent"]
            item.parents = rate["parents"]
            item.attributes = json.dumps(rate)
            if item.is_parent:
                item.is_expanded = False

        if len(context.scene.xml_rate_list) > 0:
            context.scene.xml_rate_list_active_index = 0

        return {"FINISHED"}


def create_cost_item(file, selected_rate, create_new_item=True):
    import ifcopenshell
    import bonsai

    active_ui_cost_item = bpy.context.scene.BIMCostProperties.active_cost_item
    active_ifc_cost_item = file.by_id(active_ui_cost_item.ifc_definition_id)

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
        # Remove previous cost values before updating
        if cost_item.CostValues:
            for cost_value in list(cost_item.CostValues):
                ifcopenshell.api.cost.remove_cost_value(file, parent=cost_item, cost_value=cost_value)

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
            op = row.operator(
                "xml_rate_list_ui.toggle", text="", icon=icon_expand, emboss=False
            )
            row.label(text=item.name)
            op.index = index
        else:
            # Child item
            layout.label(text="          " * item.level + item.name)

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
            
            # Apply expand/collapse logic on top of search filter
            final_flags = []
            hide_next = False
            hide_level = 10
            for i, item in enumerate(items):
                show_item = (flt_flags[i] & self.bitflag_filter_item) != 0
                
                if show_item:
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
                
                final_flags.append(self.bitflag_filter_item if show_item else 0)
            flt_flags = final_flags

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
    bl_idname = "xml_rate_list_ui.toggle"
    bl_label = "Toggle"

    index: bpy.props.IntProperty()

    def execute(self, context):
        item = context.scene.xml_rate_list[self.index]
        item.is_expanded = not item.is_expanded
        # keep the list order while expanding/collapsing by updating the active index to the toggled item
        context.scene.xml_rate_list_active_index = self.index
        return {"FINISHED"}


class CUSTOM_OT_collapse_to_level_0(Operator):
    bl_idname = "xml_rate_list_ui.collapse_to_level_0"
    bl_label = "Collapse to Level 0"

    def execute(self, context):
        items = context.scene.xml_rate_list
        for item in items:
            if item.is_parent:
                item.is_expanded = item.level < 0
        return {"FINISHED"}


class CUSTOM_OT_collapse_to_level_1(Operator):
    bl_idname = "xml_rate_list_ui.collapse_to_level_1"
    bl_label = "Collapse to Level 1"

    def execute(self, context):
        items = context.scene.xml_rate_list
        for item in items:
            if item.is_parent:
                item.is_expanded = item.level < 1
        return {"FINISHED"}


class CUSTOM_OT_expand_all(Operator):
    bl_idname = "xml_rate_list_ui.expand_all"
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
    bl_idname = "SCENE_PT_xml_rate_list"
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
        new_label += attrib["id"] + "\n"
        new_label += attrib["name"] + "\n"
        new_label += str(attrib["unit"] or "-") + "\n"
        new_label += str(round(attrib["value"], 2) or "-") + "\n"
        new_label += str(round(attrib["labor"], 2) or "-") + "\n"
        new_label += str(round(attrib["equipment"], 2) or "-") + "\n"
        new_label += str(round(attrib["materials"], 2) or "-") + "\n"
        new_label += str(round(attrib["safety"], 2) or "-") + "\n"
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
        if len(rate_info) > 5:  # arbitrary value to check the list  is populated
            row.label(text=rate_info[0])
            btn_row = row.row(align=True)
            btn_row.alignment = "RIGHT"
            btn_row.operator(
                ImportRateToActiveCostSchedule.bl_idname, text="", icon="ADD"
            )
            btn_row.operator(
                UpdateActiveCostItem.bl_idname, text="", icon="FILE_REFRESH"
            )
            row = box.row()
            box.label(text=rate_info[1])
            row = box.row()
            row.label(text="unit: " + rate_info[2])
            row.label(text="value: " + rate_info[3])
            box = layout.box()
            box.label(text="Cost Value Components:")
            row = box.row()
            row.label(text="labor: " + rate_info[4])
            row.label(text="equipment: " + rate_info[5])
            row = box.row()
            row.label(text="materials: " + rate_info[6])
            row.label(text="safety: " + rate_info[7])
            box = layout.box()
            for row in rate_info[8:]:
                box.label(text=row)


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
