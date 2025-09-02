import bpy
from bl_ui.generic_ui_list import draw_ui_list

from bonsai import tool


bpy.ops.point_cloud_visualizer.add_pcv_helper()


class LoadPC(bpy.types.Operator):
    """Tooltip"""
    bl_idname = "object.load_point_cloud"
    bl_label = "Load Point Cloud"

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        bpy.context.scene.ifc_point_cloud_list.clear()
        pcs=IfcPointCloudPanel.find_pcs()
        for item in pcs:
            list_item = bpy.context.scene.ifc_point_cloud_list.add()
            list_item.name = item.Description
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
        return {'FINISHED'}


class MyPropGroup(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()


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
            LoadPC.bl_idname, text="", icon='ADD'
        )
        draw_ui_list(
            layout,
            context,
            list_path="scene.ifc_point_cloud_list",
            active_index_path="scene.ifc_point_cloud_list_active_index",
            unique_id="ifc_point_cloud_list_id",
        )


classes = [
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

