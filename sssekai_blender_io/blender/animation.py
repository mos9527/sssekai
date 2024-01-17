from . import *

def time_to_frame(time : float):
    return int(time * bpy.context.scene.render.fps) + 1

def import_fcurve(action : bpy.types.Action, data_path : str , values : list, frames : list, num_curves : int = 1):
    '''Imports an Fcurve into an action

    Args:
        action (bpy.types.Action): target action
        data_path (str): data path
        values (list): values. size must be that of frames
        frames (list): frame indices. size must be that of values
        num_curves (int, optional): number of curves. e.g. with quaternion (W,X,Y,Z) you'd want 4. Defaults to 1.
    '''
    valueIterable = type(values[0])
    valueIterable = valueIterable != float and valueIterable != int
    assert valueIterable or (not valueIterable and num_curves == 1), "Cannot import multiple curves for non-iterable values"
    fcurve = [action.fcurves.new(data_path=data_path, index=i) for i in range(num_curves)]
    curve_data = [0] * (len(frames) * 2)
    for i in range(num_curves):
        curve_data[::2] = frames
        curve_data[1::2] = [v[i] if valueIterable else v for v in values]
        fcurve[i].keyframe_points.add(len(frames))
        fcurve[i].keyframe_points.foreach_set('co', curve_data)
        fcurve[i].update()

def import_armature_animation(name : str, data : Animation, dest_arma : bpy.types.Object):
    mesh_obj = dest_arma.children[0]
    mesh = mesh_obj.data   
    assert KEY_BONE_NAME_HASH_TBL in mesh, "Bone table not found. Invalid armature!" 
    bone_table = json.loads(mesh[KEY_BONE_NAME_HASH_TBL])
    bpy.ops.object.mode_set(mode='EDIT')
    # Collect bone space <-> local space transforms
    local_space_trans_rot = dict() # i.e. parent space
    for bone in dest_arma.data.edit_bones: # Must be done in edit mode
        local_space_trans_rot[bone.name] = (Vector(bone[KEY_BINDPOSE_TRANS]), BlenderQuaternion(bone[KEY_BINDPOSE_QUAT]))
    # from glTF-Blender-IO:
    # ---
    # We have the final TRS of the bone in values. We need to give
    # the TRS of the pose bone though, which is relative to the edit
    # bone.
    #
    #     Final = EditBone * PoseBone
    #   where
    #     Final =    Trans[ft] Rot[fr] Scale[fs]
    #     EditBone = Trans[et] Rot[er]
    #     PoseBone = Trans[pt] Rot[pr] Scale[ps]
    #
    # Solving for PoseBone gives
    #
    #     pt = Rot[er^{-1}] (ft - et)
    #     pr = er^{-1} fr
    #     ps = fs 
    # ---
    def to_pose_quaternion(bone : bpy.types.PoseBone, quat : BlenderQuaternion):
        etrans, erot = local_space_trans_rot[bone.name]
        erot_inv = erot.conjugated()
        return erot_inv @ quat
    def to_pose_translation(bone : bpy.types.PoseBone, vec : Vector):
        etrans, erot = local_space_trans_rot[bone.name]
        erot_inv = erot.conjugated()
        return erot_inv @ (vec - etrans)
    def to_pose_euler(bone : bpy.types.PoseBone, euler : Euler):
        etrans, erot = local_space_trans_rot[bone.name]
        erot_inv = erot.conjugated()
        result = erot_inv @ euler.to_quaternion()
        result = result.to_euler('XYZ') # XXX make compatible for euler interpolation
        return result
    # Reset the pose 
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.select_all(action='SELECT')
    bpy.ops.pose.transforms_clear()
    bpy.ops.pose.select_all(action='DESELECT')    
    dest_arma.animation_data_clear()
    dest_arma.animation_data_create()
    # Setup actions
    action = bpy.data.actions.new(name)
    dest_arma.animation_data.action = action
    # https://github.com/KhronosGroup/glTF-Blender-IO/issues/76
    # Batch the keyframes to load *way* faster otherwise
    for bone_hash, track in data.TransformTracks[TransformType.Rotation].items():
        # Quaternion rotations
        bone_name = bone_table[str(bone_hash)]
        bone = dest_arma.pose.bones[bone_name]
        bone.rotation_mode = 'QUATERNION'       
        values = [to_pose_quaternion(bone, swizzle_quaternion(keyframe.value)) for keyframe in track.Curve]
        # Ensure minimum rotation path (i.e. neighboring quats dots >= 0)
        for i in range(0,len(values) - 1):
            if values[i].dot(values[i+1]) < 0:
                values[i+1] = -values[i+1]
        frames = [time_to_frame(keyframe.time) for keyframe in track.Curve]
        import_fcurve(action,'pose.bones["%s"].rotation_quaternion' % bone_name, values, frames, 4)
    for bone_hash, track in data.TransformTracks[TransformType.EulerRotation].items():
        # Euler rotations
        bone_name = bone_table[str(bone_hash)]
        bone = dest_arma.pose.bones[bone_name]
        bone.rotation_mode = 'XYZ'
        values = [to_pose_euler(bone, swizzle_euler(keyframe.value)) for keyframe in track.Curve]
        frames = [time_to_frame(keyframe.time) for keyframe in track.Curve]
        import_fcurve(action,'pose.bones["%s"].rotation_euler' % bone_name, values, frames, 3)            
    for bone_hash, track in data.TransformTracks[TransformType.Translation].items():
        # Translations
        bone_name = bone_table[str(bone_hash)]
        bone = dest_arma.pose.bones[bone_name]
        values = [to_pose_translation(bone, swizzle_vector(keyframe.value)) for keyframe in track.Curve]
        frames = [time_to_frame(keyframe.time) for keyframe in track.Curve]
        import_fcurve(action,'pose.bones["%s"].location' % bone_name, values, frames, 3)       
    # No scale.

def import_keyshape_animation(name : str, data : Animation, dest_mesh : bpy.types.Object):
    mesh = dest_mesh.data
    assert KEY_SHAPEKEY_NAME_HASH_TBL in mesh, "Shape Key table not found. You can only import blend shape animations on meshes with blend shapes!"
    print(list(data.FloatTracks.keys()))
    assert BLENDSHAPES_UNK_CRC in data.FloatTracks, "No blend shape animation found!"
    keyshape_table = json.loads(mesh[KEY_SHAPEKEY_NAME_HASH_TBL])
    action = bpy.data.actions.new(name)
    mesh.shape_keys.animation_data_clear()
    mesh.shape_keys.animation_data_create()        
    mesh.shape_keys.animation_data.action = action
    for attrCRC, track in data.FloatTracks[BLENDSHAPES_UNK_CRC].items():
        bsName = keyshape_table[str(attrCRC)]
        import_fcurve(action,'key_blocks["%s"].value' % bsName, [keyframe.value / 100.0 for keyframe in track.Curve], [time_to_frame(keyframe.time) for keyframe in track.Curve])