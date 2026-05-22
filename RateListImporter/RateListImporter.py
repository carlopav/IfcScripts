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


class PriceListParser:
    title: str
    desc: str
    year: str
    language: []
    xml_rate_list: List[XmlRateItem]

    def __init__(self):
        self.xml_rate_list = []
        self.title = ""
        self.year = ""

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


class ParserXmlVeneto(PriceListParser):
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
                    "id": settore.attrib.get("cod", ""),
                    "name": settore.attrib.get("desc", ""),
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
            for capitolo in settore.findall("capitolo"):
                self.xml_rate_list.append(
                    {
                        "index": index,
                        "level": 1,
                        "is_parent": True,
                        "parents": str(n_settore),
                        "id": capitolo.attrib.get("cod", ""),
                        "name": capitolo.attrib.get("desc", ""),
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
                for paragrafo in capitolo.findall("paragrafo"):
                    children = list(paragrafo)
                    para_name = (children[0].text or "") if len(children) > 0 else ""
                    para_desc = (children[1].text or "") if len(children) > 1 else ""
                    self.xml_rate_list.append(
                        {
                            "index": index,
                            "level": 2,
                            "is_parent": True,
                            "parents": str(n_settore) + "," + str(n_capitolo),
                            "id": paragrafo.attrib.get("cod", ""),
                            "name": para_name,
                            "desc": para_desc,
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
                        try:
                            val = float(prezzo.attrib.get("val", 0))
                        except (ValueError, TypeError):
                            val = 0.0
                        try:
                            labor = float(prezzo.attrib.get("man", 0)) * val / 100
                        except (ValueError, TypeError):
                            labor = 0.0
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
                                "id": prezzo.attrib.get("cod", ""),
                                "name": prezzo.text or "",
                                "desc": para_desc,
                                "unit": prezzo.attrib.get("umi", ""),
                                "value": val,
                                "labor": labor,
                                "equipment": 0.0,
                                "materials": 0.0,
                                "safety": 0.0,
                            }
                        )
                        index += 1


class ParserXmlBasilicata(PriceListParser):
    """Parser per formato XML Basilicata (struttura gerarchica capitoli/categorie/voci/sottovoci)."""

    def parse_items(self, xml_content):
        xml_content = self.clean_xml_content(xml_content)
        root = self.get_stripped_xml_namespaces_root(xml_content)

        pdf_el = root.find('pdf')
        if pdf_el is not None and pdf_el.text:
            titolo = pdf_el.text
            if titolo.endswith('.pdf'):
                titolo = titolo[:-4]
            self.title = ' '.join(titolo.split('_'))

        capitoli = root.find('capitoli')
        if capitoli is None:
            return

        index = 0

        for capitolo in capitoli:
            codice_sc = (capitolo.findtext('codice') or '').strip()
            desc_sc = (capitolo.findtext('descrizione') or '').strip()
            self.xml_rate_list.append({
                "index": index, "level": 0, "is_parent": True, "parents": "",
                "id": codice_sc, "name": desc_sc, "desc": "", "unit": "",
                "value": 0.0, "labor": 0.0, "equipment": 0.0, "materials": 0.0, "safety": 0.0,
            })
            sc_idx = index
            index += 1

            categorie = capitolo.find('categorie')
            if categorie is None:
                continue

            for categoria in categorie:
                codice_cat_raw = (categoria.findtext('codice') or '').strip()
                codice_cat = codice_sc + '.' + codice_cat_raw
                desc_cat = (categoria.findtext('descrizione') or '').strip()
                self.xml_rate_list.append({
                    "index": index, "level": 1, "is_parent": True, "parents": str(sc_idx),
                    "id": codice_cat, "name": desc_cat, "desc": "", "unit": "",
                    "value": 0.0, "labor": 0.0, "equipment": 0.0, "materials": 0.0, "safety": 0.0,
                })
                cat_idx = index
                index += 1

                voci = categoria.find('voci')
                if voci is None:
                    continue

                for voce in voci:
                    codice_v = (voce.findtext('codice') or '').strip()
                    codice_voce = codice_cat + '.' + codice_v
                    voce_desc = (voce.findtext('descrizione') or '').strip()

                    sottovoci = voce.find('sottovoci')
                    if sottovoci is None:
                        continue

                    for sottovoce in sottovoci:
                        codice_sv = (sottovoce.findtext('codice') or '').strip()
                        sv_desc = (sottovoce.findtext('descrizione') or '').strip()
                        codice = codice_voce + '.' + codice_sv
                        desc = self.clean_string(voce_desc + ('\n- ' + sv_desc if sv_desc else ''))

                        um_el = sottovoce.find('unitaMisura')
                        um = ''
                        if um_el is not None:
                            um = (um_el.findtext('codice') or '').strip()

                        prezzo = 0.0
                        try:
                            prezzo = float(sottovoce.findtext('prezzo') or 0)
                        except (ValueError, TypeError):
                            pass

                        labor = 0.0
                        try:
                            labor = float(sottovoce.findtext('manodopera') or 0) * prezzo / 100
                        except (ValueError, TypeError):
                            pass

                        self.xml_rate_list.append({
                            "index": index, "level": 2, "is_parent": False,
                            "parents": str(sc_idx) + ',' + str(cat_idx),
                            "id": codice, "name": desc, "desc": desc, "unit": um,
                            "value": prezzo, "labor": labor,
                            "equipment": 0.0, "materials": 0.0, "safety": 0.0,
                        })
                        index += 1


class ParserXmlToscana(PriceListParser):
    """Parser per formato XML Toscana (PRT/EASY namespace variants).
    Usato anche da Calabria, Campania, Sardegna."""

    def parse_items(self, xml_content):
        xml_content = self.clean_xml_content(xml_content)
        xml_content = self._fix_namespace(xml_content)
        root = self.get_stripped_xml_namespaces_root(xml_content)

        intestazione = root.find('intestazione')
        if intestazione is not None:
            dettaglio = intestazione.find('dettaglio')
            if dettaglio is not None:
                anno = dettaglio.attrib.get('anno', '')
                area = dettaglio.attrib.get('area', '')
                self.title = f"{area} {anno}".strip()
                self.year = anno

        contenuto = root.find('Contenuto')
        if contenuto is None:
            return
        articoli = contenuto.findall('Articolo')

        index = 0
        supercat_idx = {}
        cat_idx = {}

        for articolo in articoli:
            codice = articolo.attrib.get('codice', '').strip()
            if not codice:
                continue
            parts = codice.split('.')
            if len(parts) < 2:
                continue
            codice_sc = parts[0]
            codice_cat = parts[0] + '.' + parts[1]

            supercat = (articolo.findtext('tipo') or articolo.findtext('livello1') or '').strip()
            cat = (articolo.findtext('capitolo') or articolo.findtext('livello2') or '').strip()

            if codice_sc not in supercat_idx:
                self.xml_rate_list.append({
                    "index": index, "level": 0, "is_parent": True, "parents": "",
                    "id": codice_sc, "name": supercat or codice_sc, "desc": "", "unit": "",
                    "value": 0.0, "labor": 0.0, "equipment": 0.0, "materials": 0.0, "safety": 0.0,
                })
                supercat_idx[codice_sc] = index
                index += 1

            if codice_cat not in cat_idx:
                self.xml_rate_list.append({
                    "index": index, "level": 1, "is_parent": True,
                    "parents": str(supercat_idx[codice_sc]),
                    "id": codice_cat, "name": cat or codice_cat, "desc": "", "unit": "",
                    "value": 0.0, "labor": 0.0, "equipment": 0.0, "materials": 0.0, "safety": 0.0,
                })
                cat_idx[codice_cat] = index
                index += 1

            voce = (articolo.findtext('voce') or articolo.findtext('livello3') or '').strip()
            art = (articolo.findtext('articolo') or articolo.findtext('livello4') or '').strip()
            desc = self.clean_string(voce + ('\n' + art if art else ''))

            um_el = articolo.find('um')
            um = (um_el.text or '').strip() if um_el is not None else ''
            prezzo = self._parse_price(articolo.findtext('prezzo') or '')

            labor = 0.0
            safety = 0.0
            analisi = articolo.find('Analisi')
            if analisi is not None:
                try:
                    safety = float(analisi.find('onerisicurezza').attrib.get('valore', 0))
                except Exception:
                    pass
                try:
                    labor = float(analisi.find('incidenzamanodopera').attrib.get('percentuale', 0)) * prezzo / 100
                except Exception:
                    pass

            self.xml_rate_list.append({
                "index": index, "level": 2, "is_parent": False,
                "parents": str(supercat_idx[codice_sc]) + ',' + str(cat_idx[codice_cat]),
                "id": codice, "name": desc, "desc": desc, "unit": um,
                "value": prezzo, "labor": labor, "equipment": 0.0, "materials": 0.0, "safety": safety,
            })
            index += 1

    @staticmethod
    def _fix_namespace(data):
        if '<EASY:' in data and 'xmlns:EASY=' not in data:
            tag = '<EASY:Prezzario>'
            pos = data.find(tag)
            if pos >= 0:
                ins = pos + len(tag) - 1
                data = data[:ins] + ' xmlns:EASY="mynamespace"' + data[ins:]
        if '<PRT:' in data and 'xmlns:PRT=' not in data:
            tag = '<PRT:Prezzario>'
            pos = data.find(tag)
            if pos >= 0:
                ins = pos + len(tag) - 1
                data = data[:ins] + ' xmlns:PRT="mynamespace"' + data[ins:]
        return data

    @staticmethod
    def _parse_price(text):
        if not text:
            return 0.0
        text = text.strip().replace(',', '.')
        parts = text.split('.')
        if len(parts) > 2:
            text = ''.join(parts[:-1]) + '.' + parts[-1]
        try:
            return float(text)
        except ValueError:
            return 0.0


class ParserXmlLiguria(PriceListParser):
    """Parser per formato XML Liguria (stessa struttura Toscana, differenze nei campi)."""

    def parse_items(self, xml_content):
        xml_content = self.clean_xml_content(xml_content)
        root = self.get_stripped_xml_namespaces_root(xml_content)

        intestazione = root.find('intestazione')
        if intestazione is not None:
            dettaglio = intestazione.find('dettaglio')
            if dettaglio is not None:
                anno = dettaglio.attrib.get('anno', '')
                area = dettaglio.attrib.get('area', '')
                self.title = f"{area} {anno}".strip()
                self.year = anno

        contenuto = root.find('Contenuto')
        if contenuto is None:
            return
        articoli = contenuto.findall('Articolo')

        index = 0
        supercat_idx = {}
        cat_idx = {}

        for articolo in articoli:
            codice = articolo.attrib.get('codice', '').strip()
            if not codice:
                continue
            parts = codice.split('.')
            if len(parts) < 2:
                continue
            codice_sc = parts[0]
            codice_cat = parts[0] + '.' + parts[1]

            tipo_el = articolo.find('tipo')
            supercat = (tipo_el.text or '').strip() if tipo_el is not None else ''
            cap_el = articolo.find('capitolo')
            cat = (cap_el.text or '').strip() if cap_el is not None else ''

            if codice_sc not in supercat_idx:
                self.xml_rate_list.append({
                    "index": index, "level": 0, "is_parent": True, "parents": "",
                    "id": codice_sc, "name": supercat or codice_sc, "desc": "", "unit": "",
                    "value": 0.0, "labor": 0.0, "equipment": 0.0, "materials": 0.0, "safety": 0.0,
                })
                supercat_idx[codice_sc] = index
                index += 1

            if codice_cat not in cat_idx:
                self.xml_rate_list.append({
                    "index": index, "level": 1, "is_parent": True,
                    "parents": str(supercat_idx[codice_sc]),
                    "id": codice_cat, "name": cat or codice_cat, "desc": "", "unit": "",
                    "value": 0.0, "labor": 0.0, "equipment": 0.0, "materials": 0.0, "safety": 0.0,
                })
                cat_idx[codice_cat] = index
                index += 1

            voce_el = articolo.find('voce')
            voce = (voce_el.text or '').strip() if voce_el is not None else ''
            art_el = articolo.find('articolo')
            art = (art_el.text or '').strip() if art_el is not None else ''
            desc = self.clean_string(voce + ('\n- ' + art if art else ''))

            um_el = articolo.find('um')
            um = ''
            if um_el is not None and um_el.text:
                um = um_el.text.split('(')[-1].rstrip(')').strip()

            prezzo_el = articolo.find('prezzo')
            prezzo = 0.0
            if prezzo_el is not None:
                try:
                    prezzo = float(prezzo_el.attrib.get('valore', 0))
                except (ValueError, TypeError):
                    pass

            labor = 0.0
            mo_el = articolo.find('mo')
            if mo_el is not None and mo_el.text:
                try:
                    labor = float(mo_el.text) * prezzo / 100
                except (ValueError, TypeError):
                    pass

            safety = 0.0
            sic_el = articolo.find('sicurezza')
            if sic_el is not None and sic_el.text:
                try:
                    safety = float(sic_el.text)
                except (ValueError, TypeError):
                    pass

            self.xml_rate_list.append({
                "index": index, "level": 2, "is_parent": False,
                "parents": str(supercat_idx[codice_sc]) + ',' + str(cat_idx[codice_cat]),
                "id": codice, "name": desc, "desc": desc, "unit": um,
                "value": prezzo, "labor": labor, "equipment": 0.0, "materials": 0.0, "safety": safety,
            })
            index += 1


class ParserXmlLombardia(PriceListParser):
    def parse_items(self, xml_content):
        xml_content = self.clean_xml_content(xml_content)
        root = self.get_stripped_xml_namespaces_root(xml_content)
        if root.find("voci/voci") is not None:
            self._parse_format1(root)
        else:
            self._parse_format2(root)

    def _parse_format1(self, root):
        voci_voci = root.find("voci/voci")
        rifvoce = voci_voci.find("riferimenti_voce") if voci_voci is not None else None
        if rifvoce is not None:
            import re
            parts = [rifvoce.find(t) for t in ("autore", "invigore", "anno")]
            self.title = " ".join(p.text for p in parts if p is not None and p.text)
            anno = rifvoce.find("anno")
            if anno is not None and anno.text:
                m = re.search(r"\b(\d{4})\b", anno.text)
                self.year = m.group(1) if m else ""

        voci = root.find("voci")
        if voci is None:
            return

        index = 0
        level1_idx = {}   # codifica_I → list index
        level2_idx = {}   # (codifica_I, codifica_II) → list index

        for voce in voci:
            children = list(voce)
            if len(children) < 2:
                continue
            det = children[1]

            codice = det.attrib.get("CMPcodifica_voce") or det.attrib.get("codice_voce", "")
            desc_el = det.find("declaratoria_voce")
            desc = self.clean_string(desc_el.text if desc_el is not None else "")
            um = det.attrib.get("udm_voce") or det.attrib.get("unita_misura_voce", "")

            try:
                prezzo = float(det.attrib.get("prezzo_voce", 0))
            except ValueError:
                prezzo = 0.0

            labor = 0.0
            try:
                labor = float(det.attrib.get("rapporto_RU_voce", 0)) * prezzo / 100
            except ValueError:
                pass
            if not labor:
                risorse = det.find("risorse")
                if risorse is not None:
                    for el in risorse:
                        if el.attrib.get("tipologia_risorsa") == "MANODOPERA":
                            try:
                                labor = float(el.attrib.get("perc_importo_tipo_risorsa", 0)) * prezzo / 100
                            except ValueError:
                                pass
                            break

            lvl1_cod = det.attrib.get("codifica_I_livello_voce", "")
            lvl1_des = det.attrib.get("declaratoria_I_livello_voce", "")
            lvl2_cod = det.attrib.get("codifica_II_livello_voce", "")
            lvl2_des = det.attrib.get("declaratoria_II_livello_voce", "")

            if lvl1_cod and lvl1_cod not in level1_idx:
                self.xml_rate_list.append({
                    "index": index, "level": 0, "is_parent": True, "parents": "",
                    "id": lvl1_cod, "name": lvl1_des, "desc": "", "unit": "",
                    "value": 0.0, "labor": 0.0, "equipment": 0.0, "materials": 0.0, "safety": 0.0,
                })
                level1_idx[lvl1_cod] = index
                index += 1

            key2 = (lvl1_cod, lvl2_cod)
            if lvl2_cod and lvl2_cod != lvl1_cod and key2 not in level2_idx:
                sp_parent = str(level1_idx[lvl1_cod]) if lvl1_cod in level1_idx else ""
                self.xml_rate_list.append({
                    "index": index, "level": 1 if sp_parent else 0,
                    "is_parent": True, "parents": sp_parent,
                    "id": lvl2_cod, "name": lvl2_des, "desc": "", "unit": "",
                    "value": 0.0, "labor": 0.0, "equipment": 0.0, "materials": 0.0, "safety": 0.0,
                })
                level2_idx[key2] = index
                index += 1

            parents_parts = []
            if lvl1_cod in level1_idx:
                parents_parts.append(str(level1_idx[lvl1_cod]))
            if key2 in level2_idx:
                parents_parts.append(str(level2_idx[key2]))

            self.xml_rate_list.append({
                "index": index, "level": len(parents_parts), "is_parent": False,
                "parents": ",".join(parents_parts),
                "id": codice, "name": desc, "desc": desc, "unit": um,
                "value": prezzo, "labor": labor,
                "equipment": 0.0, "materials": 0.0, "safety": 0.0,
            })
            index += 1

    def _parse_format2(self, root):
        try:
            attrs = root.items()
            if attrs:
                self.title = attrs[0][-1].split(".")[0].replace(":", "_")
        except Exception:
            pass

        index = 0
        madre_index = None

        for voce in list(root):
            codice_el = voce.find("Codice")
            if codice_el is None:
                continue
            codice = (codice_el.text or "").split(" - ")[0].strip()

            desc_el = voce.find("Declaratoria")
            desc = self.clean_string(desc_el.text if desc_el is not None else "")

            um_el = voce.find("UM")
            um = (um_el.text or "").strip() if um_el is not None else ""

            if not um:
                self.xml_rate_list.append({
                    "index": index, "level": 0, "is_parent": True, "parents": "",
                    "id": codice, "name": desc, "desc": desc, "unit": "",
                    "value": 0.0, "labor": 0.0, "equipment": 0.0, "materials": 0.0, "safety": 0.0,
                })
                madre_index = index
                index += 1
            else:
                prezzo = 0.0
                try:
                    t = voce.find("Prezzo").text.strip().replace(" €", "").replace(".", "").replace(",", ".")
                    prezzo = float(t) if t else 0.0
                except Exception:
                    pass

                labor = 0.0
                try:
                    t = voce.find("Rapporto_RU").text.strip().replace(" €", "").replace(".", "").replace(",", ".")
                    labor = float(t) if t else 0.0
                except Exception:
                    pass

                parents = str(madre_index) if madre_index is not None else ""
                self.xml_rate_list.append({
                    "index": index, "level": 1 if parents else 0, "is_parent": False,
                    "parents": parents,
                    "id": codice, "name": desc, "desc": desc, "unit": um,
                    "value": prezzo, "labor": labor,
                    "equipment": 0.0, "materials": 0.0, "safety": 0.0,
                })
                index += 1




class ParserXpwe(PriceListParser):
    """Parser per formato XPWE (Primus e compatibili)."""

    @staticmethod
    def _text(elem, path, default=""):
        try:
            found = elem.find(path)
            return (found.text or default) if found is not None else default
        except Exception:
            return default

    @staticmethod
    def _float(text):
        if not text:
            return 0.0
        try:
            return float(text.replace(",", "."))
        except (ValueError, TypeError):
            return 0.0

    def parse_items(self, xml_content):
        xml_content = self.clean_xml_content(xml_content)
        root = self.get_root(xml_content)

        dati = root.find("PweDatiGenerali")
        if dati is None:
            try:
                dati = list(root)[0].find("PweDatiGenerali")
            except Exception:
                return

        self._parse_header(dati)
        supercaps, caps = self._read_categories(dati)

        misurazioni = root.find("PweMisurazioni")
        if misurazioni is None:
            try:
                misurazioni = list(root)[0].find("PweMisurazioni")
            except Exception:
                return
        if misurazioni is None or len(list(misurazioni)) == 0:
            return

        ep_root = list(misurazioni)[0]  # PweElencoPrezzi
        ep_elements = ep_root.findall("EPItem")

        index = 0
        spcap_to_index = {}  # SuperCapitolo ID → list index
        cap_to_index = {}    # (id_spcap, id_cap) → list index

        for ep in ep_elements:
            if not ep.get("ID"):
                continue

            tariffa = self._text(ep, "Tariffa")
            if self._text(ep, "Flags") == "134217728":
                tariffa = "VDS_" + tariffa

            name = self.clean_string(self._text(ep, "DesBreve") or self._text(ep, "DesRidotta"))
            desc = self.clean_string(self._text(ep, "DesEstesa"))
            unit = self._text(ep, "UnMisura")
            prezzo_raw = self._text(ep, "Prezzo1")
            prezzo = self._float(prezzo_raw) if prezzo_raw and prezzo_raw != "0" else 0.0

            def incidenza(tag):
                val = self._float(self._text(ep, tag))
                return round(val * prezzo / 100, 6) if val else 0.0

            id_spcap = self._text(ep, "IDSpCap")
            id_cap = self._text(ep, "IDCap")

            # create SuperCapitolo on first encounter
            if id_spcap and id_spcap not in spcap_to_index:
                sc = supercaps.get(id_spcap, {})
                self.xml_rate_list.append({
                    "index": index, "level": 0, "is_parent": True, "parents": "",
                    "id": sc.get("codice", ""), "name": sc.get("desc", ""),
                    "desc": "", "unit": "", "value": 0.0,
                    "labor": 0.0, "equipment": 0.0, "materials": 0.0, "safety": 0.0,
                })
                spcap_to_index[id_spcap] = index
                index += 1

            # create Capitolo on first encounter
            cap_key = (id_spcap, id_cap)
            if id_cap and cap_key not in cap_to_index:
                cap = caps.get(id_cap, {})
                sp_parent = str(spcap_to_index[id_spcap]) if id_spcap in spcap_to_index else ""
                self.xml_rate_list.append({
                    "index": index, "level": 1 if sp_parent else 0,
                    "is_parent": True, "parents": sp_parent,
                    "id": cap.get("codice", ""), "name": cap.get("desc", ""),
                    "desc": "", "unit": "", "value": 0.0,
                    "labor": 0.0, "equipment": 0.0, "materials": 0.0, "safety": 0.0,
                })
                cap_to_index[cap_key] = index
                index += 1

            # build parents list for EPItem
            parents_parts = []
            if id_spcap in spcap_to_index:
                parents_parts.append(str(spcap_to_index[id_spcap]))
            if cap_key in cap_to_index:
                parents_parts.append(str(cap_to_index[cap_key]))

            self.xml_rate_list.append({
                "index": index,
                "level": len(parents_parts),
                "is_parent": False,
                "parents": ",".join(parents_parts),
                "id": tariffa,
                "name": name,
                "desc": desc,
                "unit": unit,
                "value": prezzo,
                "labor": incidenza("IncMDO"),
                "equipment": incidenza("IncATTR"),
                "materials": incidenza("IncMAT"),
                "safety": incidenza("IncSIC"),
            })
            index += 1

    def _parse_header(self, dati):
        try:
            child = list(dati)[0]
            content = list(child)[0] if list(child) else child
            oggetto = self._text(content, "Oggetto")
            if oggetto:
                self.title = self.clean_string(oggetto)
        except Exception:
            pass

    @staticmethod
    def _read_categories(dati):
        supercaps = {}
        caps = {}
        try:
            cap_cat = dati.find("PweDGCapitoliCategorie")
            if cap_cat is None:
                return supercaps, caps

            sc_found = cap_cat.find("PweDGSuperCapitoli")
            if sc_found is not None:
                for elem in sc_found:
                    sc_id = elem.get("ID")
                    if sc_id:
                        supercaps[sc_id] = {
                            "codice": ParserXpwe._text(elem, "Codice"),
                            "desc": ParserXpwe._text(elem, "DesSintetica"),
                        }

            cap_found = cap_cat.find("PweDGCapitoli")
            if cap_found is not None:
                for elem in cap_found:
                    cap_id = elem.get("ID")
                    if cap_id:
                        desc = ParserXpwe._text(elem, "DesSintetica")
                        if desc == "Nuova voce":
                            desc = ParserXpwe._text(elem, "DesEstesa")
                        caps[cap_id] = {
                            "codice": ParserXpwe._text(elem, "Codice"),
                            "desc": desc,
                        }
        except Exception:
            pass
        return supercaps, caps


class ParserXmlSix(PriceListParser):
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

        prz_desc = prezzario.find("przDescrizione")
        if prz_desc is not None:
            self.title = self.clean_string(prz_desc.attrib.get("breve", ""))

        self.default_list_id = self._get_default_quotazione_id(prezzario)
        units = self.get_units(prezzario)
        products = prezzario.findall("prodotto")

        # sort by prdId ensures parents are always processed before their children
        products = sorted(products, key=lambda p: p.attrib.get("prdId", ""))

        index = 0
        prdId_to_index = {}

        for product in products:
            prdId = product.attrib.get("prdId", "")
            level = self.get_level_from_prdId(product)
            is_parent = self.is_parent(product)

            if is_parent:
                prdId_to_index[prdId] = str(index)

            # build parents as comma-separated ancestor indices from root to immediate parent
            parts = prdId.split(".")
            ancestors = [".".join(parts[:i]) for i in range(1, len(parts))]
            parents = ",".join(prdId_to_index[p] for p in ancestors if p in prdId_to_index)

            desc = product.find("prdDescrizione")
            name = self.clean_string(desc.attrib.get("breve", "")) if desc is not None else ""
            description = self.clean_string(desc.attrib.get("estesa", "")) if desc is not None else ""
            cost_value = self.get_value(product)

            self.xml_rate_list.append({
                "index": index,
                "level": level,
                "is_parent": is_parent,
                "parents": parents,
                "id": prdId,
                "name": name,
                "desc": description,
                "unit": self.get_unit(units, product),
                "value": cost_value,
                "labor": self.get_value_component(product, cost_value, "incidenzaManodopera"),
                "equipment": self.get_value_component(product, cost_value, "incidenzaAttrezzatura"),
                "materials": self.get_value_component(product, cost_value, "incidenzaMateriali"),
                "safety": self._get_safety(product, cost_value),
            })
            index += 1

    def _get_default_quotazione_id(self, prezzario):
        lista = prezzario.find("listaQuotazione")
        if lista is not None:
            return lista.attrib.get("listaQuotazioneId")
        return None

    @staticmethod
    def _get_safety(product, cost_value):
        try:
            return float(product.attrib.get("onereSicurezza", 0)) * cost_value / 100
        except (ValueError, TypeError):
            return 0.0

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
        if component_type not in ("incidenzaManodopera", "incidenzaMateriali", "incidenzaAttrezzatura"):
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
        quotazioni = product.findall("prdQuotazione")
        if not quotazioni:
            return True
        return all(float(q.attrib.get("valore", 0)) == 0.0 for q in quotazioni)


class ParserIfcCostSchedule(PriceListParser):
    """Parser per IfcCostSchedule — progetto corrente o file IFC esterno."""

    def parse_schedule(self, file, schedule_id):
        import ifcopenshell.util.cost as cost_util
        schedule = file.by_id(int(schedule_id))
        self.title = schedule.Name or f"Schedule {schedule_id}"
        root_items = cost_util.get_root_cost_items(schedule)
        index = 0

        def _val(cost_item):
            for cv in (cost_item.CostValues or []):
                try:
                    v = cv.AppliedValue
                    if v is not None:
                        return float(v.wrappedValue if hasattr(v, 'wrappedValue') else v)
                except Exception:
                    pass
            return 0.0

        def _labor(cost_item):
            for cv in (cost_item.CostValues or []):
                for sub in (getattr(cv, 'Components', None) or []):
                    if getattr(sub, 'Category', None) == 'Labor':
                        try:
                            v = sub.AppliedValue
                            return float(v.wrappedValue if hasattr(v, 'wrappedValue') else v)
                        except Exception:
                            pass
            return 0.0

        def traverse(cost_item, level, parent_indices):
            nonlocal index
            has_children = bool(cost_item.IsNestedBy)
            self.xml_rate_list.append({
                "index": index,
                "ifc_id": cost_item.id(),
                "level": level,
                "is_parent": has_children,
                "parents": ",".join(str(p) for p in parent_indices),
                "id": cost_item.Identification or "",
                "name": cost_item.Name or "",
                "desc": cost_item.Description or "",
                "unit": "",
                "value": _val(cost_item),
                "labor": _labor(cost_item),
                "equipment": 0.0,
                "materials": 0.0,
                "safety": 0.0,
            })
            current_index = index
            index += 1
            for rel in (cost_item.IsNestedBy or []):
                for child in rel.RelatedObjects:
                    traverse(child, level + 1, parent_indices + [current_index])

        for root_item in root_items:
            traverse(root_item, 0, [])


# ---------------------------------------------------------------------------
# Recent files support
# ---------------------------------------------------------------------------

_recent_cache = []  # module-level: prevents GC of enum item strings
_importing = False  # guard against recursive import triggered by setting xml_rate_recent_path


def _recent_file_path():
    import os
    return os.path.join(bpy.utils.user_resource('CONFIG'), 'RateListImporter_recent.json')


def _load_recent():
    try:
        with open(_recent_file_path(), 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def _save_recent(path, title, year):
    entries = _load_recent()
    entries = [e for e in entries if e['path'] != path]
    entries.insert(0, {'path': path, 'title': title, 'year': year})
    entries = entries[:10]
    try:
        with open(_recent_file_path(), 'w', encoding='utf-8') as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _refresh_recent_cache():
    global _recent_cache
    entries = _load_recent()
    if entries:
        _recent_cache = [
            (
                e['path'],
                f"{e['title']} ({e['year']})" if e.get('year') else e['title'],
                e['path'],
            )
            for e in entries
        ]
    else:
        _recent_cache = [('__NONE__', '— nessun prezzario recente —', '')]


def _get_recent_items(self, context):
    return _recent_cache or [('__NONE__', '— nessun prezzario recente —', '')]


def _on_recent_select(self, context):
    global _importing
    if _importing:
        return
    path = self.xml_rate_recent_path
    if path and path != '__NONE__':
        _do_import(path, context)


# ---------------------------------------------------------------------------
# IFC project schedule source
# ---------------------------------------------------------------------------

_ifc_schedules_cache = []


def _refresh_ifc_schedules_cache():
    global _ifc_schedules_cache
    try:
        from bonsai import tool
        file = tool.Ifc.get()
        if file is None:
            _ifc_schedules_cache = [('__NONE__', '— nessun schedule IFC —', '')]
            return
        schedules = file.by_type("IfcCostSchedule")
        _ifc_schedules_cache = [
            (str(s.id()), s.Name or f"Schedule {s.id()}", "")
            for s in schedules
        ] or [('__NONE__', '— nessun schedule IFC —', '')]
    except Exception:
        _ifc_schedules_cache = [('__NONE__', '— nessun schedule IFC —', '')]


def _get_ifc_schedules(self, context):
    return _ifc_schedules_cache or [('__NONE__', '— nessun schedule IFC —', '')]


def _on_ifc_schedule_select(self, context):
    schedule_id = self.ifc_rate_source_schedule
    if schedule_id and schedule_id != '__NONE__':
        _do_import_ifc(schedule_id, context)
    else:
        context.scene.xml_rate_list.clear()


def _on_source_mode_change(self, context):
    if self.rate_source_mode == 'FILE':
        path = context.scene.xml_rate_recent_path
        if path and path != '__NONE__':
            _do_import(path, context)
        else:
            context.scene.xml_rate_list.clear()
    else:
        _refresh_ifc_schedules_cache()
        schedule_id = context.scene.ifc_rate_source_schedule
        if schedule_id and schedule_id != '__NONE__':
            _do_import_ifc(schedule_id, context)
        else:
            context.scene.xml_rate_list.clear()


# ---------------------------------------------------------------------------
# Core parser detection and import logic
# ---------------------------------------------------------------------------

def _find_xml_parser(xml_content):
    """From Leeno (thanks Giuserpe): pre-scans the XML to pick the right parser."""
    parsers = {
        "PweDatiGenerali": ParserXpwe,
        'xmlns="six.xsd"': ParserXmlSix,
        'autore="Regione Toscana"': ParserXmlToscana,
        'autore="Regione Calabria"': ParserXmlToscana,
        'autore="Regione Campania"': ParserXmlToscana,
        'autore="Regione Sardegna"': ParserXmlToscana,
        'autore="Regione Liguria"': ParserXmlLiguria,
        "rks=": ParserXmlVeneto,
        "<settore cod=": ParserXmlVeneto,
        "<pdf>Prezzario_Regione_Basilicata": ParserXmlBasilicata,
        "<autore>Regione Lombardia": ParserXmlLombardia,
        "<autore>LOM": ParserXmlLombardia,
    }
    for pattern, parser_class in parsers.items():
        if pattern in xml_content:
            return parser_class
    return None


def _populate_list_from_parser(parser, context):
    context.scene.xml_rate_title = parser.title
    context.scene.xml_rate_year = parser.year
    context.scene.xml_rate_list.clear()
    for rate in parser.xml_rate_list:
        item = context.scene.xml_rate_list.add()
        if rate["is_parent"] and rate["name"].startswith("Group "):
            item.name = rate["id"]
        else:
            item.name = (rate["id"] + " - " + rate["name"]).strip(" -") or f"Item {rate['index']}"
        item.level = rate["level"]
        item.is_parent = rate["is_parent"]
        item.parents = rate["parents"]
        item.attributes = json.dumps(rate)
        if item.is_parent:
            item.is_expanded = False
    if len(context.scene.xml_rate_list) > 0:
        context.scene.xml_rate_list_active_index = 0


def _do_import(filepath, context, report=None):
    import os, re
    xml_content = PriceListParser.get_xml_content(filepath)
    parser_class = _find_xml_parser(xml_content)
    if parser_class is None:
        if report:
            report({'ERROR'}, "Cannot automatically find a parser for selected file")
        return False

    parser = parser_class()
    parser.parse_items(xml_content)

    filename = os.path.basename(filepath)
    name = os.path.splitext(filename)[0]
    match = re.search(r'\b(\d{4})\b', name)
    parser.year = match.group(1) if match else ""
    parser.title = name

    _populate_list_from_parser(parser, context)

    _save_recent(filepath, parser.title, parser.year)
    _refresh_recent_cache()
    global _importing
    _importing = True
    try:
        context.scene.xml_rate_recent_path = filepath
    finally:
        _importing = False
    return True


def _do_import_ifc(schedule_id, context, report=None):
    try:
        from bonsai import tool
        file = tool.Ifc.get()
        if file is None:
            if report:
                report({'ERROR'}, "No IFC file loaded")
            return False
    except Exception as e:
        if report:
            report({'ERROR'}, str(e))
        return False

    parser = ParserIfcCostSchedule()
    parser.parse_schedule(file, schedule_id)
    _populate_list_from_parser(parser, context)
    return True


class ImportRateList(Operator, ImportHelper):
    """Import an Italian regional price list (prezzario) in XML or XPWE format."""

    bl_idname = "import.rate_list"
    bl_label = "Import Rate List"
    filename_ext = ".xml"
    filter_glob: bpy.props.StringProperty(
        default="*.xml;*.xpwe",
        options={"HIDDEN"},
        maxlen=255,
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

    def execute(self, context):
        success = _do_import(self.filepath, context, self.report)
        return {"FINISHED"} if success else {"CANCELLED"}


def get_parent_desc(selected_rate):
    rate_attrib = json.loads(selected_rate.attributes)
    parent_indices = [p for p in rate_attrib.get("parents", "").split(",") if p.strip()]
    if not parent_indices:
        return ""
    parent_idx = int(parent_indices[-1])
    items = bpy.context.scene.xml_rate_list
    if parent_idx < len(items):
        return json.loads(items[parent_idx].attributes).get("desc", "")
    return ""


def create_cost_item(file, selected_rate, create_new_item=True, combine_desc=False):
    from bonsai import tool
    import ifcopenshell.util.cost
    import bonsai.bim.module.cost.data

    active_ui_cost_item = bpy.context.scene.BIMCostProperties.active_cost_item
    active_ifc_cost_item = file.by_id(active_ui_cost_item.ifc_definition_id)

    if create_new_item:
        if active_ifc_cost_item in ifcopenshell.util.cost.get_root_cost_items(
            file.by_id(bpy.context.scene.BIMCostProperties.active_cost_schedule_id)
        ):
            cost_item = tool.Ifc.run("cost.add_cost_item", cost_item=active_ifc_cost_item)
        elif active_ui_cost_item.has_children:
            cost_item = tool.Ifc.run("cost.add_cost_item", cost_item=active_ifc_cost_item)
        else:
            cost_item = tool.Ifc.run("cost.add_cost_item", cost_item=active_ifc_cost_item.Nests[0].RelatingObject)
    else:
        cost_item = active_ifc_cost_item
        if cost_item.CostValues:
            for cost_value in list(cost_item.CostValues):
                tool.Ifc.run("cost.remove_cost_value", parent=cost_item, cost_value=cost_value)

    rate_attrib = json.loads(selected_rate.attributes)
    if combine_desc:
        parent_desc = get_parent_desc(selected_rate)
        desc = (parent_desc + "\n" + rate_attrib["desc"]).strip() if parent_desc else rate_attrib["desc"]
    else:
        desc = rate_attrib["desc"]

    tool.Ifc.run("cost.edit_cost_item", cost_item=cost_item, attributes={
        "Identification": rate_attrib["id"],
        "Name": rate_attrib["name"],
        "Description": desc,
    })

    labor = float(rate_attrib["labor"])
    equipment = float(rate_attrib["equipment"])
    materials = float(rate_attrib["materials"])
    safety = float(rate_attrib["safety"])
    total_value = float(rate_attrib["value"])

    components = [
        ("Labor", labor),
        ("Equipment", equipment),
        ("Materials", materials),
        ("Safety", safety),
    ]
    has_components = any(v != 0.0 for _, v in components)

    if not has_components:
        cost_value = tool.Ifc.run("cost.add_cost_value", parent=cost_item)
        tool.Ifc.run("cost.edit_cost_value", cost_value=cost_value, attributes={"AppliedValue": round(total_value, 2)})
    else:
        remaining = round(total_value - sum(v for _, v in components), 2)
        if remaining != 0.0:
            cost_value = tool.Ifc.run("cost.add_cost_value", parent=cost_item)
            tool.Ifc.run("cost.edit_cost_value", cost_value=cost_value, attributes={"AppliedValue": remaining})
        for category, amount in components:
            if amount != 0.0:
                cost_value = tool.Ifc.run("cost.add_cost_value", parent=cost_item)
                tool.Ifc.run("cost.edit_cost_value", cost_value=cost_value, attributes={
                    "Category": category,
                    "AppliedValue": round(amount, 2),
                })

    bonsai.bim.module.cost.data.refresh()
    tool.Cost.load_cost_schedule_tree()


try:
    from bonsai import tool as _bonsai_tool
    _IfcOperatorBase = (_bonsai_tool.Ifc.Operator, bpy.types.Operator)
    del _bonsai_tool
except Exception:
    _IfcOperatorBase = (bpy.types.Operator,)


class UpdateActiveCostItem(*_IfcOperatorBase):
    """Update active cost item with selected rate data."""

    bl_idname = "import.xml_rate_update_cost_item"
    bl_label = "Update active cost item"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        try:
            props = bpy.context.scene.BIMCostProperties
            return (
                len(getattr(bpy.context.scene, "xml_rate_list", [])) > 0
                and props.active_cost_schedule_id != 0
                and props.active_cost_item is not None
            )
        except:
            return False

    def _execute(self, context):
        from bonsai import tool
        selected_rate = bpy.context.scene.xml_rate_list[bpy.context.scene.xml_rate_list_active_index]
        file = tool.Ifc.get()
        create_cost_item(file, selected_rate=selected_rate, create_new_item=False,
            combine_desc=context.scene.xml_rate_combine_desc)


class ImportRateToActiveCostSchedule(*_IfcOperatorBase):
    """Add a new cost item to the active schedule with selected rate data."""

    bl_idname = "import.xml_rate_add_cost_item"
    bl_label = "Import Rate to Active Cost Schedule"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        try:
            props = bpy.context.scene.BIMCostProperties
            return (
                len(getattr(bpy.context.scene, "xml_rate_list", [])) > 0
                and props.active_cost_schedule_id != 0
                and props.active_cost_item is not None
            )
        except:
            return False

    def _execute(self, context):
        from bonsai import tool
        selected_rate = bpy.context.scene.xml_rate_list[bpy.context.scene.xml_rate_list_active_index]
        file = tool.Ifc.get()
        create_cost_item(file, selected_rate=selected_rate, create_new_item=True,
            combine_desc=context.scene.xml_rate_combine_desc)


class AssignRateValue(*_IfcOperatorBase):
    """Assign the selected rate as the cost value of the active cost item."""

    bl_idname = "import.xml_rate_assign_cost_value"
    bl_label = "Assign Cost Rate Value"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        try:
            if context.scene.rate_source_mode != 'IFC_SCHEDULE':
                return False
            props = context.scene.BIMCostProperties
            if str(props.active_cost_schedule_id) == context.scene.ifc_rate_source_schedule:
                return False
            if props.active_cost_schedule_id == 0 or props.active_cost_item is None:
                return False
            selected = context.scene.xml_rate_list[context.scene.xml_rate_list_active_index]
            return json.loads(selected.attributes).get("ifc_id", 0) != 0
        except:
            return False

    def _execute(self, context):
        from bonsai import tool
        from bonsai.core import cost as cost_core
        import bonsai.bim.module.cost.data
        selected = context.scene.xml_rate_list[context.scene.xml_rate_list_active_index]
        ifc_id = json.loads(selected.attributes).get("ifc_id", 0)
        file = tool.Ifc.get()
        cost_item = file.by_id(context.scene.BIMCostProperties.active_cost_item.ifc_definition_id)
        cost_rate = file.by_id(ifc_id)
        cost_core.assign_cost_value(tool.Ifc, tool.Cost, cost_item=cost_item, cost_rate=cost_rate)
        bonsai.bim.module.cost.data.refresh()
        tool.Cost.load_cost_schedule_tree()


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
                    for parent_idx in [int(p) for p in item.parents.split(",") if p.strip()]:
                        search_filtered_flags[parent_idx] = self.bitflag_filter_item
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
    bl_label = "Rate List Importer"
    bl_idname = "SCENE_PT_xml_rate_list"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Rate List"
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
        row = layout.row(align=True)
        row.prop(context.scene, "rate_source_mode", expand=True)
        row = layout.row(align=True)
        if context.scene.rate_source_mode == 'FILE':
            row.prop(context.scene, "xml_rate_recent_path", text="")
            row.operator(ImportRateList.bl_idname, text="", icon="ADD")
        else:
            row.prop(context.scene, "ifc_rate_source_schedule", text="")
            row.operator(IFC_OT_rate_source_refresh.bl_idname, text="", icon="FILE_REFRESH")
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
            btn_row.prop(context.scene, "xml_rate_combine_desc", text="", icon="OUTLINER", toggle=True)
            btn_row.separator(factor=2.0)
            btn_row.operator(
                ImportRateToActiveCostSchedule.bl_idname, text="", icon="ADD"
            )
            btn_row.operator(
                UpdateActiveCostItem.bl_idname, text="", icon="FILE_REFRESH"
            )
            btn_row.operator(
                AssignRateValue.bl_idname, text="", icon="COPYDOWN"
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


class IFC_OT_rate_source_refresh(Operator):
    bl_idname = "ifc_rate_source.refresh"
    bl_label = "Refresh Schedules"

    def execute(self, context):
        _refresh_ifc_schedules_cache()
        schedule_id = context.scene.ifc_rate_source_schedule
        if schedule_id and schedule_id != '__NONE__':
            _do_import_ifc(schedule_id, context)
        return {"FINISHED"}


classes = [
    XmlRateCustomUIList,
    CUSTOM_OT_toggle,
    CUSTOM_OT_collapse_to_level_0,
    CUSTOM_OT_collapse_to_level_1,
    CUSTOM_OT_expand_all,
    IFC_OT_rate_source_refresh,
    UpdateActiveCostItem,
    ImportRateToActiveCostSchedule,
    AssignRateValue,
    ImportRateList,
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
    bpy.types.Scene.xml_rate_title = bpy.props.StringProperty(name="Rate Title", default="")
    bpy.types.Scene.xml_rate_year = bpy.props.StringProperty(name="Rate Year", default="")
    bpy.types.Scene.xml_rate_combine_desc = bpy.props.BoolProperty(
        name="Combine Description with Parent",
        description="Prepend the parent item description to the selected item description",
        default=False,
    )
    bpy.types.Scene.xml_rate_recent_path = bpy.props.EnumProperty(
        name="Recent Price Lists",
        description="Recently opened price lists — select to load",
        items=_get_recent_items,
        update=_on_recent_select,
    )
    bpy.types.Scene.rate_source_mode = bpy.props.EnumProperty(
        name="Source",
        items=[
            ('FILE', "External Rate List", "Load from XML or XPWE file"),
            ('IFC_SCHEDULE', "Current Project Rate List", "Load from a cost schedule in the current IFC project"),
        ],
        default='FILE',
        update=_on_source_mode_change,
    )
    bpy.types.Scene.ifc_rate_source_schedule = bpy.props.EnumProperty(
        name="IFC Rate Schedule",
        description="Select a cost schedule from the current IFC project as rate source",
        items=_get_ifc_schedules,
        update=_on_ifc_schedule_select,
    )
    _refresh_recent_cache()
    _refresh_ifc_schedules_cache()


def unregister():
    class_unregister()
    del bpy.types.Scene.xml_rate_list
    del bpy.types.Scene.xml_rate_list_active_index
    del bpy.types.Scene.xml_rate_title
    del bpy.types.Scene.xml_rate_year
    del bpy.types.Scene.xml_rate_combine_desc
    del bpy.types.Scene.xml_rate_recent_path
    del bpy.types.Scene.rate_source_mode
    del bpy.types.Scene.ifc_rate_source_schedule


register()
