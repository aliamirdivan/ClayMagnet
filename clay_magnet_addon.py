# Clay Magnet - Making animators' lives easier!
# Copyright (c) 2025 Ali Amirdivan
# GNU GPL v3, check it out: https://www.gnu.org/licenses/gpl-3.0.html
# Built with love for rigging warriors by Ali Amirdivan

bl_info = {
    "name": "Clay Magnet",
    "author": "Ali Amirdivan",
    "version": (1, 23),
    "blender": (4, 1, 0),
    "location": "View3D > Sidebar > Clay Magnet",
    "description": "Tag and select bones with F/Shift+F, Gizmo User mode for animators",
    "category": "Animation",
}

import bpy
import mathutils
import bpy_extras
import math

# Store tagged bones globally (per armature)
tagged_bones = {}

class CLAYMAGNET_Preferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    hitbox_size: bpy.props.FloatProperty(
        name="Hitbox Size",
        description="Pixel radius for bone hover detection",
        default=50.0,
        min=10.0,
        max=100.0,
    )

    restrict_pose_mode: bpy.props.BoolProperty(
        name="Restrict Panel to Pose Mode",
        description="Show panel only in Pose Mode",
        default=False,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "hitbox_size")
        layout.prop(self, "restrict_pose_mode")

# Tag bones for hover selection
class CLAYMAGNET_OT_tag_bone(bpy.types.Operator):
    """Tag selected bones so they can be grabbed with F/Shift+F"""
    bl_idname = "clay_magnet.tag_bone"
    bl_label = "Tag Bone(s)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        armature = context.object
        if not armature or armature.type != 'ARMATURE':
            self.report({'ERROR'}, "Select an armature first!")
            return {'CANCELLED'}

        if armature not in tagged_bones:
            tagged_bones[armature] = set()

        for bone in context.selected_pose_bones or []:
            tagged_bones[armature].add(bone.name)
            print(f"Tagged {bone.name} for {armature.name}")  # Debug cheer

        return {'FINISHED'}

# Untag bones
class CLAYMAGNET_OT_untag_bone(bpy.types.Operator):
    """Remove tags from selected bones"""
    bl_idname = "clay_magnet.untag_bone"
    bl_label = "Untag Bone(s)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        armature = context.object
        if not armature or armature.type != 'ARMATURE':
            self.report({'ERROR'}, "Need an armature, buddy!")
            return {'CANCELLED'}

        if armature in tagged_bones:
            for bone in context.selected_pose_bones or []:
                tagged_bones[armature].discard(bone.name)
                print(f"Untagged {bone.name} from {armature.name}")  # Bye tag!

        return {'FINISHED'}

# Filter to tagged bones
class CLAYMAGNET_OT_find_tagged(bpy.types.Operator):
    """Keep only tagged bones selected"""
    bl_idname = "clay_magnet.find_tagged"
    bl_label = "Find Tagged"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        armature = context.object
        if not armature or armature.type != 'ARMATURE':
            self.report({'ERROR'}, "Pick an armature first!")
            return {'CANCELLED'}

        if armature in tagged_bones:
            for bone in armature.pose.bones:
                bone.bone.select = bone.name in tagged_bones[armature]
            print(f"Showing only tagged bones for {armature.name}")  # Tag party!

        return {'FINISHED'}

# Switch selected armatures to Pose Mode
class CLAYMAGNET_OT_switch_pose_mode(bpy.types.Operator):
    """Set all selected armatures to Pose Mode"""
    bl_idname = "clay_magnet.switch_pose_mode"
    bl_label = "Switch to Pose Mode"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        armatures = [obj for obj in context.selected_objects if obj.type == 'ARMATURE']
        if not armatures:
            self.report({'ERROR'}, "Select some armatures first!")
            return {'CANCELLED'}

        for armature in armatures:
            bpy.context.view_layer.objects.active = armature
            bpy.ops.object.mode_set(mode='POSE')
            print(f"Flipped {armature.name} to Pose Mode")  # Pose time!

        return {'FINISHED'}

# Select and transform bones with F/Shift+F
class CLAYMAGNET_OT_select_transform(bpy.types.Operator):
    """F to grab bones, Shift+F to stack 'em up!"""
    bl_idname = "clay_magnet.select_transform"
    bl_label = "Select/Transform Bone"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE' and context.object.mode == 'POSE'

    def invoke(self, context, event):
        # Snag the mouse spot
        mouse_pos = mathutils.Vector((event.mouse_region_x, event.mouse_region_y))
        region = context.region
        rv3d = context.region_data

        # Find the closest tagged bone
        armature = context.object
        closest_bone = None
        closest_dist = float('inf')
        hitbox_size = context.preferences.addons[__name__].preferences.hitbox_size

        if armature in tagged_bones:
            for bone_name in tagged_bones[armature]:
                try:
                    bone = armature.pose.bones[bone_name]
                    bone_center = bone.head

                    # Try custom shape center if it exists
                    if bone.custom_shape:
                        try:
                            mesh = bone.custom_shape
                            verts = [armature.matrix_world @ mesh.matrix_world @ v.co for v in mesh.data.vertices]
                            if verts:
                                bone_center = sum(verts, mathutils.Vector()) / len(verts)
                                print(f"Got {bone_name} custom shape at {bone_center}")  # Custom shape win!
                        except Exception as e:
                            print(f"Whoops, {bone_name}'s custom shape messed up: {e}")  # Shape fail

                    # Project bone to screen
                    screen_pos = bpy_extras.view3d_utils.location_3d_to_region_2d(region, rv3d, bone_center)
                    if screen_pos:
                        dist = (mouse_pos - screen_pos).length
                        if dist < hitbox_size and dist < closest_dist:
                            closest_dist = dist
                            closest_bone = bone
                except Exception as e:
                    print(f"Oops, skipped {bone_name}: {e}")  # Bone glitch

        if closest_bone:
            bone = closest_bone
            bone.bone.select = True
            # Shift+F adds to selection, F selects and maybe transforms
            if not event.shift:
                for other_bone in armature.pose.bones:
                    if other_bone != bone:
                        other_bone.bone.select = False
                # Transform only if Gizmo User is off
                gizmo_user = context.scene.clay_magnet_gizmo_user
                if not gizmo_user:
                    context.view_layer.objects.active = armature
                    bpy.ops.transform.translate('INVOKE_DEFAULT')
            print(f"Picked {bone.name} with {'Shift+' if event.shift else ''}F")  # Bone grabbed!

        return {'FINISHED'}

# Sidebar panel for Clay Magnet
class CLAYMAGNET_PT_panel(bpy.types.Panel):
    """Clay Magnet controls for tagging and selecting bones"""
    bl_label = "Clay Magnet"
    bl_idname = "PT_ClayMagnet"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Clay Magnet"

    @classmethod
    def poll(cls, context):
        preferences = context.preferences.addons[__name__].preferences
        if preferences.restrict_pose_mode:
            return context.object and context.object.mode == 'POSE'
        return True

    def draw(self, context):
        layout = self.layout
        # Took ages to get multi-armature right!
        armatures = [obj for obj in context.selected_objects if obj.type == 'ARMATURE']

        if not armatures:
            layout.label(text="Select an armature!", icon='ERROR')
            return

        layout.operator("clay_magnet.switch_pose_mode", icon='POSE_HLT')

        if context.object and context.object.mode == 'POSE':
            box = layout.box()
            box.label(text="Tagging", icon='BOOKMARKS')
            box.operator("clay_magnet.tag_bone", icon='ADD')
            box.operator("clay_magnet.untag_bone", icon='REMOVE')
            box.operator("clay_magnet.find_tagged", icon='VIEWZOOM')

            box = layout.box()
            box.label(text="Options", icon='SETTINGS')
            box.prop(context.scene, "clay_magnet_gizmo_user", text="Gizmo User")

# Gizmo User property
def register_properties():
    bpy.types.Scene.clay_magnet_gizmo_user = bpy.props.BoolProperty(
        name="Gizmo User",
        description="F only selects, no transform, for gizmo lovers",
        default=False,
    )

def unregister_properties():
    del bpy.types.Scene.clay_magnet_gizmo_user

# Keymap setup
keymaps = []

def register():
    # Register classes and properties
    for cls in [
        CLAYMAGNET_Preferences,
        CLAYMAGNET_OT_tag_bone,
        CLAYMAGNET_OT_untag_bone,
        CLAYMAGNET_OT_find_tagged,
        CLAYMAGNET_OT_switch_pose_mode,
        CLAYMAGNET_OT_select_transform,
        CLAYMAGNET_PT_panel,
    ]:
        bpy.utils.register_class(cls)

    register_properties()

    # Set up keymap for F and Shift+F
    wm = bpy.context.window_manager
    km = wm.keyconfigs.addon.keymaps.new(name='Pose', space_type='EMPTY')
    kmi = km.keymap_items.new(
        CLAYMAGNET_OT_select_transform.bl_idname,
        'F',
        'PRESS',
        shift=False,
    )
    keymaps.append((km, kmi))
    kmi = km.keymap_items.new(
        CLAYMAGNET_OT_select_transform.bl_idname,
        'F',
        'PRESS',
        shift=True,
    )
    keymaps.append((km, kmi))
    print("Clay Magnet ready to roll!")  # Addon’s alive!

def unregister():
    # Clean up keymap
    for km, kmi in keymaps:
        km.keymap_items.remove(kmi)
    keymaps.clear()

    # Unregister classes and properties
    for cls in reversed([
        CLAYMAGNET_Preferences,
        CLAYMAGNET_OT_tag_bone,
        CLAYMAGNET_OT_untag_bone,
        CLAYMAGNET_OT_find_tagged,
        CLAYMAGNET_OT_switch_pose_mode,
        CLAYMAGNET_OT_select_transform,
        CLAYMAGNET_PT_panel,
    ]):
        bpy.utils.unregister_class(cls)

    unregister_properties()
    print("Clay Magnet signing off!")  # Peace out

if __name__ == "__main__":
    register()