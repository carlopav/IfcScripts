import bpy
from bonsai.bim.ifc import IfcStore


def format_bool(python_bool):
    if python_bool == True:
        return "true"
    return "false"


def compile_pdf_with_typst(file_path, exporter):
    #import tempfile
    import os
    from bonsai import tool
    from ifc5d.ifc5Dspreadsheet import Ifc5DCsvWriter
    import typst
    
    file = IfcStore.get_file()
    project = file.by_type("IfcProject")[0]
    schedule=file.by_type("IfcCostSchedule")[int(exporter.chosen_schedule)]
    
    
    ''' export csv'''
    writer = Ifc5DCsvWriter(file=tool.Ifc.get(), output=os.path.dirname(file_path), cost_schedule=schedule)
    writer.write()
    csv_filename = schedule.Name + ".csv"
    
    ''' chose typst template based on schedule PredefinedType, 
    should locate the file also or copy it to working folder'''
    if schedule.PredefinedType == 'PRICEDBILLOFQUANTITIES' or schedule.PredefinedType == 'UNPRICEDBILLOFQUANTITIES' :
        typst_template_path = "template_priced_bill_of_quantities.typ"
            
    elif schedule.PredefinedType == 'SCHEDULEOFRATES':
        print("Not supported yet")
        return
        
    else:
        print("Not supported yet")
        return
        
    
    content =  ''
    content += '#import "{}": *\n'.format(typst_template_path)
    content += '#show: project.with(\n'
    content += 'schedule_path: "{}",\n'.format(csv_filename)
    content += 'title: "{}",\n'.format(project.Name)
    content += 'schedule_name: "{}",\n'.format(schedule.Name)
    content += 'cover_page: {},\n'.format("false")
    content += 'root_items_to_new_page: {},\n'.format("false")
    content += 'summary: {},\n'.format(format_bool(exporter.should_print_summary)) # controllare che il formato si "false" e non "False" o 0
    content += ")"

    ''' write main.typ content and compile it'''
    typst_main_path = os.path.join(os.path.dirname(file_path), "main.typ")
    with open(typst_main_path, "w") as typ_file:
        typ_file.write(content)

    pdf_bytes = typst.compile(typst_main_path)
    
    ''' Clean temporary files '''
    ''' os.unlink(temp_path)  # rimuovi file temporaneo'''
    os.remove(typst_main_path)
    os.remove(os.path.join(os.path.dirname(file_path), csv_filename))
    
    # Salva il PDF
    with open(file_path, "wb") as f:
        f.write(pdf_bytes)
    
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
        
        
    @classmethod
    def poll(cls, context):
        try:
            import typst
            return True
        except:
            return False
        
        
    def execute(self, context):
        #return print_schedule_to_pdf(context, self.filepath, self)#, self.should_print_description)
        return compile_pdf_with_typst(self.filepath, self)
    
    
# Only needed if you want to add into a dynamic menu
def menu_func_export(self, context):
    self.layout.operator(ExportIfcCostSchedule.bl_idname, text="IfcCostSchedule to PDF")


# Register and add to the "file selector" menu (required to use F3 search "Text Export Operator" for quick access).
def register():
    bpy.utils.register_class(ExportIfcCostSchedule)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export) # to change based on button position


def unregister():
    bpy.utils.unregister_class(ExportIfcCostSchedule)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export) # to change based on button position


if __name__ == "__main__":
    register()

    # test call
    bpy.ops.export_test.some_data('INVOKE_DEFAULT')
