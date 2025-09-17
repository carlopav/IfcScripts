import bpy
from bl_ui.generic_ui_list import draw_ui_list

from bpy_extras.io_utils import ImportHelper

from bonsai import tool


def get_ifc_document_references():
    model = tool.Ifc.get()
    ifc_document_references=[]
    for ref in model.by_type("IfcDocumentReference"):
        if ref.Location and ref.Location[-3:] in ("e57","ply"):
            ifc_document_references.append(ref)
    return ifc_document_references


def update_point_clouds_list():
    bpy.context.scene.ifc_point_cloud_list.clear()
    ifc_document_references=get_ifc_document_references()
    for document_reference in ifc_document_references:
        list_item = bpy.context.scene.ifc_point_cloud_list.add()
        list_item.name = document_reference.Description
        list_item.ifc_definition_id=document_reference.id()
        related_objects = ifc_document_reference_get_related_objects(document_reference)
        if len(related_objects) > 0:
            list_item.has_related_object = True
            bl_obj = tool.Ifc.get_object(related_objects[0])
            assign_pcv_properties(bl_obj, document_reference.Location)
        else:
            list_item.has_related_object = False


def ifc_document_reference_has_reated_objects(ifc_object):
    if not ifc_object.is_a("IfcDocumentReference"):
        return False
    for rel in ifc_object.DocumentRefForObjects:
        for obj in rel.RelatedObjects:
            return True
    return False


def ifc_document_reference_get_related_objects(ifc_object):
    if not ifc_object.is_a("IfcDocumentReference"):
        return []
    related_objects=[]
    for rel in ifc_object.DocumentRefForObjects:
        for obj in rel.RelatedObjects:
            related_objects.append(obj)
    return related_objects
    

def assign_pcv_properties(bl_object, filepath):
    try:
        import point_cloud_visualizer as pcv
        if(object):
            props = bl_object.point_cloud_visualizer
            props.data.filepath = bpy.path.abspath(filepath)#'//points.ply')
            props.data.filetype = 'PLY'
    except:
        print("ERROR: Not able to assing Point Cloud Visualizer properties to blender object.\n")


def create_related_ifc_annotation(ifc_ref):
    
    bpy.ops.object.empty_add(type='PLAIN_AXES')
    bpy.context.active_object.name = ifc_ref.Description
    bpy.ops.bim.assign_class(ifc_class="IfcAnnotation")
    bpy.ops.bim.assign_container()
    
    file = tool.Ifc.get()
    import ifcopenshell
    ifc_annotation = tool.Ifc.get_entity(bpy.context.active_object)
    ifcopenshell.api.document.assign_document(file, products=[ifc_annotation], document=ifc_ref)
    

def show_point_cloud(bl_object):
    import point_cloud_visualizer as pcv
    props = bl_object.point_cloud_visualizer
    pd = pcv.mechanist.PCVStoker.load(props, operator=None, )
    if(pd):
        pcv.mechanist.PCVMechanist.init()
        pcv.mechanist.PCVMechanist.data(bl_object, pd, draw=True, )
        pcv.mechanist.PCVMechanist.tag_redraw()


def hide_point_cloud(bl_object):
    return



class PCUIListItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name")


class PCUIList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        layout.prop(item, "name", text="", emboss=False)
        if item.has_related_object:
            layout.operator(SelectPCReferenceObject.bl_idname, text="", icon="RESTRICT_SELECT_OFF")
        else:
            layout.operator(CreateIfcAnnotationProxy.bl_idname, text="", icon="ADD")
            

class SelectPCReferenceObject(bpy.types.Operator):
    """Select linked object. If more than one object is related, just the first is selected."""
    bl_idname = "bim.select_pointcloud_object"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Select reference related object"
    
    def execute(self, context):
        file = tool.Ifc.get()
        ifc_id = bpy.context.scene.ifc_point_cloud_list[bpy.context.scene.ifc_point_cloud_list_active_index].ifc_definition_id
        ifc_ref = file.by_id(ifc_id)
        bl_obj = None
        for rel in ifc_ref.DocumentRefForObjects:
            for obj in rel.RelatedObjects:
                bl_obj = tool.Ifc.get_object(obj)
        if bl_obj:
            bpy.ops.object.select_all(action='DESELECT')
            bl_obj.select_set(True)
            bpy.context.view_layer.objects.active = bl_obj
        return {'FINISHED'}
    
    
class AddPC(bpy.types.Operator, ImportHelper):
    """Add Point Cloud reference to current Ifc"""
    bl_idname = "import_test.some_data"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Import Some Data"

    # ImportHelper mix-in class uses this.
    filename_ext = ".ply"

    filter_glob: bpy.props.StringProperty(
        default="*.ply",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def execute(self, context):
        
        return {'FINISHED'}


class TogglePCEditing(bpy.types.Operator):
    """Add Point Cloud reference to current Ifc"""
    bl_idname = "bim.toggle_point_cloud_editing"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Load the saved Point Clouds in this IFC Project."

    def execute(self, context):
        bpy.context.scene.ifc_point_cloud_panel_is_editing = not bpy.context.scene.ifc_point_cloud_panel_is_editing
        return {'FINISHED'}


class CreateIfcAnnotationProxy(bpy.types.Operator):
    """Created a related IfcAnnotation."""
    bl_idname = "bim.create_related_ifc_annotation_proxy"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Created a related object to store point cloud positioning using a IfcAnnotation."

    def execute(self, context):
        file=tool.Ifc.get()
        ifc_id = bpy.context.scene.ifc_point_cloud_list[bpy.context.scene.ifc_point_cloud_list_active_index].ifc_definition_id
        create_related_ifc_annotation(file.by_id(ifc_id))
        update_point_clouds_list()
        return {'FINISHED'}
    
    
class LoadPC(bpy.types.Operator):
    """Loads the point cloud with Point Cloud Visualizer addon."""
    bl_idname = "object.load_point_cloud"
    bl_label = "Load Point Cloud"

    @classmethod
    def poll(cls, context):
        try:
            import point_cloud_visualizer
            return True
        except:
            return false
    
    
    def execute(self, context):
        file = tool.Ifc.get()
        ifc_id = bpy.context.scene.ifc_point_cloud_list[bpy.context.scene.ifc_point_cloud_list_active_index].ifc_definition_id
        ifc_ref = file.by_id(ifc_id)
        proxies = []
        for rel in ifc_ref.DocumentRefForObjects:
            for obj in rel.RelatedObjects:
                proxies.append(obj)
        if len(proxies) == 0:
            create_related_ifc_annotation(ifc_ref)
            assign_pcv_properties(bpy.context.active_object, ifc_ref.Location)
            show_point_cloud(bl_obj)
        for ifc_obj in proxies:
            bl_obj = tool.Ifc.get_object(ifc_obj)
            assign_pcv_properties(bl_obj, ifc_ref.Location)
            show_point_cloud(bl_obj)
        
        return {'FINISHED'}


class HideAllPCs(bpy.types.Operator):
    """Loads the point cloud with Point Cloud Visualizer addon."""
    bl_idname = "object.hide_all_point_clouds"
    bl_label = "Hide All Point Clouds in the model"

    @classmethod
    def poll(cls, context):
        try:
            import point_cloud_visualizer
            return True
        except:
            return false
    
    def execute(self, context):
        
        return {'FINISHED'}

class UpdatePointCloudsList(bpy.types.Operator):
    """Tooltip"""
    bl_idname = "bim.update_point_clouds_list"
    bl_label = "Update Point Cloud List"

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        update_point_clouds_list()
        return {'FINISHED'}


class PCItemPropGroup(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    ifc_definition_id: bpy.props.IntProperty()
    has_related_object: bpy.props.BoolProperty()
    

class IfcPointCloudPanel(bpy.types.Panel):
    bl_label = "Point Clouds"
    bl_idname = "BIM_PT_pointclouds"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"
    bl_order = 1
        
    def draw(self, context):
        layout = self.layout
        if bpy.context.scene.ifc_point_cloud_panel_is_editing:
            row = layout.row()
            row.label(text="Update list:")
            btn_row = row.row(align=True)
            btn_row.alignment = "RIGHT"
            btn_row.operator(
                UpdatePointCloudsList.bl_idname, text="", icon='FILE_REFRESH'
            )
            btn_row.operator(
                AddPC.bl_idname, text="", icon='ADD'
            )
            btn_row.operator(
                LoadPC.bl_idname, text="", icon='HIDE_OFF'
            )
            btn_row.operator(
                HideAllPCs.bl_idname, text="", icon='HIDE_ON'
            )
            btn_row.operator(TogglePCEditing.bl_idname, text="", icon="CANCEL")
                        
            layout.template_list("PCUIList", "", 
                           bpy.context.scene, "ifc_point_cloud_list", 
                           bpy.context.scene, "ifc_point_cloud_list_active_index")
        else:
            row = layout.row()
            row.label(icon="OUTLINER_DATA_POINTCLOUD", text="O Point Clouds Found")
            btn_row = row.row(align=True)
            btn_row.alignment = "RIGHT"
            btn_row.operator(
                TogglePCEditing.bl_idname, text="", icon='IMPORT'
            )
            

classes = [
CreateIfcAnnotationProxy,
    HideAllPCs,
    SelectPCReferenceObject,
    PCUIList, PCUIListItem,
    TogglePCEditing,
    AddPC,
    LoadPC,
    UpdatePointCloudsList,
    PCItemPropGroup,
    IfcPointCloudPanel,
]

class_register, class_unregister = bpy.utils.register_classes_factory(classes)


def register():
    class_register()
    bpy.types.Scene.ifc_point_cloud_list = bpy.props.CollectionProperty(type=PCItemPropGroup)
    bpy.types.Scene.ifc_point_cloud_list_active_index = bpy.props.IntProperty()
    bpy.types.Scene.ifc_point_cloud_panel_is_editing = bpy.props.BoolProperty(default=False)


def unregister():
    class_unregister()
    del bpy.types.Scene.ifc_point_cloud_list
    del bpy.types.Scene.ifc_point_cloud_list_active_index
    del bpy.types.Scene.ifc_point_cloud_panel_is_editing


register()

