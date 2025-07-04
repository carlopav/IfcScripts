from fpdf import FPDF
import textwrap
import ifcopenshell as ios
from bonsai.bim.ifc import IfcStore
from datetime import datetime
import bpy

class SchedulePDF(FPDF):
    def __init__(self, file, project, cost_schedule):
        super().__init__()
        self.set_auto_page_break(auto=False)
        self.bottom_margin = 15
        self.row_height = 4
        
        # project and schedule reference
        self.file = file
        self.project = project
        self.cost_schedule = cost_schedule
        
        # output parameters
        self.category_level_to_new_page = 0
        self.should_print_summary = False
        self.should_print_single_quantities = True
        
        self.quantity_value_attributes = ['AreaValue', 'VolumeValue', 'LengthValue', 'CountValue', 'WeightValue', 'TimeValue']
        self.has_cover = False
        
        if self.cost_schedule.PredefinedType == 'PRICEDBILLOFQUANTITIES' or self.cost_schedule.PredefinedType == 'UNPRICEDBILLOFQUANTITIES' :
            self.col_headers = ['N°', 'Description', 'n°', 'a', 'b', 'c/w', 'Quantity', 'Price', 'Total']
            self.col_widths = [15, 55, 15, 15, 15, 15, 20, 20, 20] # total width 190
            
        elif self.cost_schedule.PredefinedType == 'SCHEDULEOFRATES':
            self.col_headers = ['N°', 'Description', 'Price']
            self.col_widths = [15, 155, 20]
            
        else:
            print("Not supported yet")
            return
        
        
    def restore_text_default(self):
        self.set_font('Arial', '', 8)
        
        
    def add_formatted_page(self):
        self.line(10, self.get_y(), 200, self.get_y())
        self.add_page()
        self.draw_table_header()
            
        
    def draw_cover_page(self):
        self.has_cover = True
        self.add_page()
        
        #header        
        self.set_y(10)
        self.set_font('Arial', 'B', 18)
        self.cell(w=0, h=30, txt=self.cost_schedule.Name, border="LTRB", align='C')
        self.set_font('Arial', '', 12)
        
        #body
        self.set_margins(left=12, top=12, right=12)
        self.set_y(150)
        self.set_font('Arial', '', 12)
        self.cell(w=50, h=5, txt="Project:", align='L')
        self.multi_cell(w=140, h=5, txt=self.project.Name, align='L')
        self.ln()
        self.cell(w=50, h=5, txt="Description:", align='L')
        self.multi_cell(w=140, h=5, txt=self.project.Description, align='L')
        self.ln()
        self.cell(w=50, h=5, txt="Phase:", align='L')
        self.multi_cell(w=140, h=5, txt=self.project.Phase, align='L')
        
        #footer
        self.set_y(240)
        self.cell(w=50, h=5, txt="Date:", align='L')
        self.cell(w=140, h=5, txt=datetime.now().strftime("%d/%m/%Y"), align='L')
        self.set_y(260)
        self.cell(w=50, h=5, txt="Author:", align='L')
        self.cell(w=140, h=5, txt="..................................................", align='L')
        
        #body
        self.line(10,  42, 10,  287)
        self.line(200,  42, 200,  287)
        self.line(10,  42, 200,  42)
        self.line(10,  287, 200,  287)
                
        self.restore_text_default()
        
        
    def header(self):
        """Header on each page"""
        if self.has_cover and self.page_no() > 1:
            
            self.set_margins(10, 10, 10)
            
            self.set_font('Arial', '', 10)
            self.cell(0, 10, self.project.Name, align='L')
            self.set_xy(10, 10)  # Torna all'inizio della riga
            self.cell(0, 10, self.cost_schedule.Name, align='R')
            self.restore_text_default()
            self.ln(15)  # Spazio dopo l'intestazione
        
        
    def footer(self):
        """Footer on each page"""
        if self.has_cover and self.page_no() == 1:
            return
        
        elif self.has_cover and self.page_no() > 1:
            self.set_y(-15)  # Posizione a 15mm dal fondo
            self.set_font('Arial', '', 8)
        
            # Date
            date_str = datetime.now().strftime("%d/%m/%Y")
            self.cell(0, 10, date_str, align='L')
            
            # Page number
            self.set_x(10)
            page_str = f"page {self.page_no()-1}" # TODO: non riesco ad avere il totale pagine corretto se ho la copertina
            self.cell(0, 10, page_str, align='R') 
            
        elif not self.has_cover:
            self.set_y(-15)  # Posizione a 15mm dal fondo
            self.set_font('Arial', '', 8)
        
            # Date
            date_str = datetime.now().strftime("%d/%m/%Y")
            self.cell(0, 10, date_str, align='L')
            
            # Page number
            self.set_x(10)
            page_str = f"page {self.page_no()}/{{nb}}"
            self.cell(0, 10, page_str, align='R')
        
        
    def draw_category(self, index, name):
        self.set_font('Arial', 'B', 10)
        self.add_table_row([index, name, "", "", "", "", "", ""])
    
    
    def draw_cost_item(self, index, name, rate_id):
        if self.cost_schedule.PredefinedType == 'PRICEDBILLOFQUANTITIES' or self.cost_schedule.PredefinedType == 'UNPRICEDBILLOFQUANTITIES':
            self.set_font('Arial', 'B', 8)
            self.add_table_row([index, name, "", "", "", "", "", ""])
            if rate_id:
                self.set_font('Arial', 'I', 8)
                self.add_table_row(["",  rate_id, "", "", "", "", "", "", ""])
        else:
            pass

    
    def draw_description(self, description):
        self.restore_text_default()
        if description:
            self.add_table_row(["", description, "", "", "", "", "", ""])
        pass
    
    
    def draw_quantities(self, quantities, print_each_quantity=True):
        self.set_font('Arial', '', 8)
        unit = ''
        if not quantities: return unit
        for quantity in quantities:
            if hasattr(quantity, "Name"): quantity_name = quantity.Name
            else: quantity_name = ''
            for attr in self.quantity_value_attributes:
                if hasattr(quantity, attr):
                    quantity_value = "%.2f" % round(getattr(quantity, attr),2)
                    if not quantity_value:
                        quantity_value = 'error'
            # evaluate formula if present (TODO: make it more robust, at the moment formula should be
            #                                    formatted in this way: x*y*z*w; also should check
            #                                    if quantity value is corresponding)
            formula = getattr(quantity, "Formula")
            if formula:
                formula_components = []
                try: 
                    list=formula.split("*")
                    for txt in list:
                        formula_components.append("%.2f" % round(float(txt), 2))
                    if len(formula_components) != 4:
                        formula_components = ["","","",""]
                except:
                    formula_components = ["","","",""]
            else: 
                formula_components = ["","","",""]
            # print quantities
            if print_each_quantity:
                self.add_table_row(["", "- "+ quantity_name, formula_components[0], formula_components[1], formula_components[2], formula_components[3], quantity_value, ""])
            try: 
                if unit == '': 
                    unit = ios.util.unit.get_property_unit(quantity, self.file).Name
            except: pass
        return unit
    
    
    def draw_cost_item_totals(self, cost_item, unit, should_print_rates=True):
        # TODO: trovare un modo più serio per calcolare il totale della voce
        self.set_font('Arial', '', 8)
        total_quantity = ios.util.cost.get_total_quantity(cost_item)
        if not total_quantity: total_quantity = 0.0
        costs = cost_item.CostValues
        if costs:
            cost_value = costs[0].AppliedValue
            if cost_value:
                cost = cost_value.wrappedValue # modificare per avere il total cost
                total_cost = total_quantity*cost
            else:
                cost = 0.0
                total_cost = 0.0
        else:
            cost = 0.0
            total_cost = 0.0
            
        self.line(10 + sum(self.col_widths)-sum(self.col_widths[-3:]),  self.get_y(), 10 + sum(self.col_widths),  self.get_y())
        if should_print_rates == False or self.cost_schedule.PredefinedType == 'UNPRICEDBILLOFQUANTITIES':
            # do not print rates and total
            self.add_table_row(["", "Sum "+unit, "" , "", "", "", "%.2f" % (round(total_quantity,2)),"______", "______"])
        else:
            # print rates and total
            self.add_table_row(["", "Sum "+unit, "" , "", "", "", "%.2f" % (round(total_quantity,2)),str(cost), str(round(total_quantity*cost,2))])
            

    def draw_summary(self):
        """Print summary costs page TODO: finish function"""
        self.add_page()
        self.draw_table_header()
        root_costs = list(ios.util.cost.get_root_cost_items(self.cost_schedule))
        self.set_font('Arial', '', 10)
        counter = 1
        total_cost = 0.0
        for root_cost in root_costs:
            try:
                cost_values = ios.util.cost.get_cost_values(root_cost)
                cost_value = cost_values[0]["label"]
                total_cost += float(cost_value[:-8])
            except:
                cost_value = "0.00"
            self.add_table_row([str(counter), root_cost.Name , "", "", "", "", "","", cost_value[:-8]])
            counter += 1
        self.add_table_row(["", "" , "", "", "", "", "","", ""])
        self.set_font('Arial', 'B', 10)
        self.add_table_row(['', 'Total' , "", "", "", "", "","", "%.2f" % (round(total_cost,2))])
        self.add_table_row(["", "" , "", "", "", "", "","", ""])
        self.line(10, self.get_y(), 200, self.get_y())
    
        
    def draw_table_header(self):
        if self.get_y() < 15:  # Se siamo all'inizio pagina
            self.set_y(15)
            
        self.set_font('Arial', 'B', 8)
        self.set_fill_color(220, 220, 220)
        
        for header, width in zip(self.col_headers, self.col_widths):
            self.cell(width, 8, header, border=1, align='C', fill=True)
        self.ln()
        self.restore_text_default()
        self.add_table_row(["", "", "", "", "", "", "", ""])
    
    
    def get_remaining_space(self):
        return self.h - self.get_y() - self.bottom_margin
    
    
    def wrap_text_for_columns(self, data):
        wrapped_columns = []
        
        for i, (text, width) in enumerate(zip(data, self.col_widths)):
            # Calcola caratteri per riga basato sulla larghezza colonna
            chars_per_line = max(1, int(width * 0.4))
            
            if i == 1:  # Colonna descrizione - più conservativo
                chars_per_line = max(1, int(width * 0.7))
            
            wrapped_text = textwrap.wrap(str(text), width=chars_per_line)
            if not wrapped_text:
                wrapped_text = ['']
            wrapped_columns.append(wrapped_text)
        
        return wrapped_columns
    
    
    def add_table_row(self, data):
        """Add a line with possible text interruption to new page"""
        
        # Prepara il testo wrappato
        wrapped_columns = self.wrap_text_for_columns(data)
        
        # Trova la colonna con più righe
        max_lines = max(len(lines) for lines in wrapped_columns)
        
        # Processa riga per riga
        lines_processed = 0
        
        while lines_processed < max_lines:
            # Controlla spazio disponibile
            space_available = self.get_remaining_space()
            
            if space_available < self.row_height:
                # Non c'è spazio, nuova pagina
                self.add_formatted_page()
                continue
            
            # Calcola quante righe possiamo disegnare
            max_lines_in_page = int(space_available / self.row_height)
            remaining_lines = max_lines - lines_processed
            lines_to_draw = min(max_lines_in_page, remaining_lines)
            
            # Disegna le righe
            self.draw_table_section(wrapped_columns, lines_processed, lines_to_draw, type)
            
            lines_processed += lines_to_draw
            
            # Se abbiamo finito, esci
            if lines_processed >= max_lines:
                break
            
            # Altrimenti vai alla pagina successiva
            self.add_formatted_page()
    
    
    def draw_table_section(self, wrapped_columns, start_line, num_lines, type):
        """Disegna una sezione della tabella"""
        start_y = self.get_y()
        section_height = num_lines * self.row_height
        
        # Disegna i bordi esterni delle celle
        x_offset = 10
        for width in self.col_widths:
            # Bordo sinistro
            self.line(x_offset, start_y, x_offset, start_y + section_height)
            x_offset += width
        
        # Bordo destro finale
        self.line(x_offset, start_y, x_offset, start_y + section_height)
        
        # Bordi orizzontali tra celle
        # self.line(10, start_y, 10 + sum(col_widths), start_y)  # Top
        # self.line(10, start_y + section_height, 10 + sum(col_widths), start_y + section_height)  # Bottom
        
        # Riempie il contenuto
        for col_idx, (lines, width) in enumerate(zip(wrapped_columns, self.col_widths)):
            x_pos = 10 + sum(self.col_widths[:col_idx])
            
            # Allineamento
            if col_idx in [0, 3, 4, 5, 6, 7, 8]:  # Colonne numeriche
                align = 'C'
            else:
                align = 'L'
            if type == 'item_sum':
                align = 'R'
            # Disegna ogni riga di testo
            for line_idx in range(num_lines):
                actual_line_idx = start_line + line_idx
                
                if actual_line_idx < len(lines):
                    text = lines[actual_line_idx]
                else:
                    text = ''
                
                # Posizione del testo
                text_y = start_y + (line_idx * self.row_height)
                self.set_xy(x_pos + 1, text_y + 1)
                
                # Scrivi il testo
                self.cell(width - 2, self.row_height - 2, text, align=align)
        
        # Sposta il cursore
        self.set_y(start_y + section_height)



def print_schedule_to_pdf(context, filepath, exporter):
    
    def print_nested_cost_items(file, pdf, parent, parent_counter):
        childs = list(ios.util.cost.get_nested_cost_items(parent))
        counter=1
        for cost_item in childs:
            
            index = parent_counter+"."+str(counter)
            pdf.draw_cost_item(index = index, name = cost_item.Name, rate_id = cost_item.Identification)
            if exporter.should_print_description:
                pdf.draw_description(description = cost_item.Description)
            unit = pdf.draw_quantities(quantities = cost_item.CostQuantities, print_each_quantity=exporter.should_print_each_quantity)
            pdf.draw_cost_item_totals(cost_item, unit, exporter.should_print_rates)
            
            pdf.add_table_row(["", "", "" , "", "", "", "", "", ""])
            
            print_nested_cost_items(file, pdf, cost_item, index)
            counter += 1
            
        return childs
    
    file = IfcStore.get_file()
    project = file.by_type("IfcProject")[0]
    schedule=file.by_type("IfcCostSchedule")[int(exporter.chosen_schedule)]
    
    pdf = SchedulePDF(file, project, schedule)
        
    if exporter.should_print_cover:
        pdf.draw_cover_page()
    
    pdf.add_page()
    pdf.draw_table_header()
    
    root_costs = list(ios.util.cost.get_root_cost_items(schedule))
    counter = 1
    for root_cost in root_costs:
        counter
        pdf.draw_category(str(counter), root_cost.Name)
        print_nested_cost_items(file, pdf, root_cost, str(counter))
        counter += 1
        
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    
    if exporter.should_print_summary: pdf.draw_summary()
    
    pdf.output(filepath)
    print(f"File creato")
    return {'FINISHED'}



# BLENDER INTERFACE TO SELECT FILE AND OPTIONS

from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator


class ExportIfcCostSchedule(Operator, ExportHelper):
    """This appears in the tooltip of the operator and in the generated docs"""
    bl_idname = "export_test.some_data"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Export IfcCostSchedule"

    # ExportHelper mix-in class uses this.
    filename_ext = ".pdf"

    filter_glob: StringProperty(
        default="*.pdf",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    # List of operator properties, the attributes will be assigned
    # to the class instance from the operator settings before calling.
    
    file = IfcStore.get_file()
    schedules=file.by_type("IfcCostSchedule")
    counter = 0
    schedule_names = ()
    for schedule in schedules:
        schedule_names += ((str(counter), schedule.Name + ' (' + schedule.PredefinedType + ')', '',),)
        counter +=1
    chosen_schedule: EnumProperty(
        name="",
        description="Choose between two items",
        items=schedule_names,
        default='0',
    )

    should_print_cover: BoolProperty(
        name="Should print document cover",
        description="Create a cover page with project data",
        default=False,
    )
    should_print_description: BoolProperty(
        name="Should print description",
        description="Export the full description if present",
        default=True,
    )
    
    should_print_each_quantity: BoolProperty(
        name="Should print each quantity",
        description="Export the full list of quantities",
        default=True,
    )   
    
    should_print_rates: BoolProperty(
        name="Should print rates and totals",
        description="Print rates and totals for each voice",
        default=True,
    )   
    
    should_print_summary: BoolProperty(
        name="Should print summary",
        description="Print summary at the end of the document",
        default=True,
    )   

    
    '''should_print_categories_to_new_page: BoolProperty(
        name="Categories to new page",
        description="Export the full description if present",
        default=True,
    )'''
    
    
    def draw(self, context):
        """Disegna l'interfaccia delle opzioni"""
        layout = self.layout
        
        # Sezione opzioni di export
        box = layout.box()
        box.label(text="Select Ifc Cost Schedule:")
        box.prop(self, "chosen_schedule")
        
        
        # Separatore
        layout.separator()

        box = layout.box()
        box.label(text="Export properties:")
        box.prop(self, "should_print_cover")
        box.prop(self, "should_print_description")
        box.prop(self, "should_print_each_quantity")
        box.prop(self, "should_print_summary")

        # Altro pulsante esempio
        row = box.row()
        row.operator("export_scene.reset_options", text="Reset Opzioni", icon='FILE_REFRESH')
        
        
    def execute(self, context):
        return print_schedule_to_pdf(context, self.filepath, self)#, self.should_print_description)

    
# Only needed if you want to add into a dynamic menu
def menu_func_export(self, context):
    self.layout.operator(ExportIfcCostSchedule.bl_idname, text="IfcCostSchedule to PDF")


# Register and add to the "file selector" menu (required to use F3 search "Text Export Operator" for quick access).
def register():
    bpy.utils.register_class(ExportIfcCostSchedule)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(ExportIfcCostSchedule)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()

    # test call
    bpy.ops.export_test.some_data('INVOKE_DEFAULT')
