import bpy
from bl_ui.generic_ui_list import draw_ui_list

from bpy_extras.io_utils import ImportHelper

from bonsai import tool


bpy.ops.point_cloud_visualizer.add_pcv_helper()

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
        return read_some_data(context, self.filepath, self.use_setting)

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
    
    @staticmethod
    def assign_pcv_properties(object, filepath):
        print(filepath)
        import point_cloud_visualizer as pcv
        
        if(object):
            props = object.point_cloud_visualizer
            props.data.filepath = bpy.path.abspath(filepath)#'//points.ply')
            props.data.filetype = 'PLY'
            pd = pcv.mechanist.PCVStoker.load(props, operator=None, )
            if(pd):
                pcv.mechanist.PCVMechanist.init()
                pcv.mechanist.PCVMechanist.data(object, pd, draw=True, )
                pcv.mechanist.PCVMechanist.tag_redraw()
    
    def execute(self, context):
        file = tool.Ifc.get()
        ifc_id = bpy.context.scene.ifc_point_cloud_list[bpy.context.scene.ifc_point_cloud_list_active_index].ifc_definition_id
        ifc_ref = file.by_id(ifc_id)
        proxies = []
        for rel in ifc_ref.DocumentRefForObjects:
            for obj in rel.RelatedObjects:
                proxies.append(obj)
        if len(proxies) == 0:
            bpy.ops.object.empty_add(type='PLAIN_AXES')
            bpy.context.active_object.name = ifc_ref.Description
            bpy.ops.bim.assign_class(ifc_class="IfcAnnotation")
            bpy.ops.bim.assign_container()
            LoadPC.assign_pcv_properties(bpy.context.active_object, ifc_ref.Location)
        for ifc_obj in proxies:
            bl_obj = tool.Ifc.get_object(ifc_obj)
            LoadPC.assign_pcv_properties(bl_obj, ifc_ref.Location)
        
        return {'FINISHED'}


class UpdateLinked_PC(bpy.types.Operator):
    """Tooltip"""
    bl_idname = "object.simple_operator"
    bl_label = "Update Point Cloud List"

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        bpy.context.scene.ifc_point_cloud_list.clear()
        pcs=IfcPointCloudPanel.find_pcs()
        for item in pcs:
            list_item = bpy.context.scene.ifc_point_cloud_list.add()
            list_item.name = item.Description
            list_item.ifc_definition_id=item.id()
        return {'FINISHED'}


class MyPropGroup(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    ifc_definition_id: bpy.props.IntProperty()


class IfcPointCloudPanel(bpy.types.Panel):
    bl_label = "Ifc Point Cloud Reference"
    bl_idname = "IfcPointCloudPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "IfcPC"
    
    @staticmethod
    def find_pcs():
        model = tool.Ifc.get()
        pcs=[]
        for ref in model.by_type("IfcDocumentReference"):
            if ref.Location and ref.Location[-3:] in ("e57","ply"):
                pcs.append(ref)
        return pcs
    
    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.label(text="Update list:")
        btn_row = row.row(align=True)
        btn_row.alignment = "RIGHT"
        btn_row.operator(
            UpdateLinked_PC.bl_idname, text="", icon='FILE_REFRESH'
        )
        btn_row.operator(
            AddPC.bl_idname, text="", icon='ADD'
        )
        btn_row.operator(
            LoadPC.bl_idname, text="", icon='HIDE_OFF'
        )
        
        draw_ui_list(
            layout,
            context,
            list_path="scene.ifc_point_cloud_list",
            active_index_path="scene.ifc_point_cloud_list_active_index",
            unique_id="ifc_point_cloud_list_id",
        )


classes = [
    AddPC,
    LoadPC,
    UpdateLinked_PC,
    MyPropGroup,
    IfcPointCloudPanel,
]

class_register, class_unregister = bpy.utils.register_classes_factory(classes)


def register():
    class_register()
    bpy.types.Scene.ifc_point_cloud_list = bpy.props.CollectionProperty(type=MyPropGroup)
    bpy.types.Scene.ifc_point_cloud_list_active_index = bpy.props.IntProperty()


def unregister():
    class_unregister()
    del bpy.types.Scene.ifc_point_cloud_list
    del bpy.types.Scene.ifc_point_cloud_list_active_index


register()

