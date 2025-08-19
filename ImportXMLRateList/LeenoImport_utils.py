"""
    LeenO - helpers modulo di importazione prezzari
"""

from io import StringIO
import xml.etree.ElementTree as ET

import LeenoImport_XmlSix
import LeenoImport_XmlToscana
import LeenoImport_XmlSardegna
import LeenoImport_XmlLiguria
import LeenoImport_XmlVeneto
import LeenoImport_XmlBasilicata
import LeenoImport_XmlLombardia


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
