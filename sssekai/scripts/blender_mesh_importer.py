import bpy
import bmesh
# HACK: to get blender to use the system's python packges
import sys
sys.path.append(r'C:\Users\mos9527\AppData\Local\Programs\Python\Python310\Lib\site-packages')
print(sys.path)
from UnityPy import Environment, config
from UnityPy.enums import ClassIDType
from UnityPy.classes import Mesh, SkinnedMeshRenderer, MeshRenderer, GameObject, Transform
from UnityPy.math import Vector3, Quaternion
from typing import List, Dict
from sssekai.unity import SEKAI_UNITY_VERSION # XXX: expandusr does not work in Blender!
config.FALLBACK_UNITY_VERSION = SEKAI_UNITY_VERSION
from sssekai.abcache import AbCache, AbCacheConfig
import os,zlib
from collections import defaultdict
from dataclasses import dataclass
@dataclass
class Bone:
    name : str
    localPosition : Vector3
    localRotation : Quaternion
    localScale : Vector3
    children : list # Bone
    global_path : str = ''
    global_transform = None # XXX not needed
@dataclass
class Armature:
    name : str
    skinned_mesh_gameobject : GameObject = None
    root : Bone = None
# TODO: Make these things prompts / configs
cache_cfg = AbCacheConfig(None, r'C:\Users\mos9527\.sssekai\abcache')
cache = AbCache(cache_cfg)
bundle_path = cache_cfg.cache_dir + r'\live_pv\model\character\body\21\0001\ladies_s'
bundle = cache.index.get_bundle_by_abcache_path(cache_cfg, bundle_path)
env = Environment(bundle.get_file_path(cache_cfg))
# Collect all static meshes and skinned meshes's *root transform*
# UnityPy does not construct the Scene Hierarchy so we have to do it ourselves
static_mesh_gameobjects : List[GameObject] = list() # No extra care needed
transform_roots = []
for asset in env.assets:
    for obj in asset.get_objects():
        data = obj.read()
        if obj.type == ClassIDType.GameObject and getattr(data,'m_MeshRenderer',None):
            static_mesh_gameobjects.append(data)
        if obj.type == ClassIDType.Transform:
            if hasattr(data,'m_Children') and not data.m_Father.path_id:
                transform_roots.append(data)
# Collect all skinned meshes as Armature[s]
# Note that Mesh maybe reused across Armatures
armatures : Dict[str,Armature] = dict()
bone_path_tbl : Dict[int, Bone] = dict()
for root in transform_roots:
    armature = Armature(root.m_GameObject.read().m_Name)
    def dfs(root : Transform, parent : Bone = None):
        gameObject = root.m_GameObject.read()
        name = gameObject.m_Name        
        if getattr(gameObject,'m_SkinnedMeshRenderer',None):
            armature.skinned_mesh_gameobject = gameObject
        path_from_root = ''
        if parent and parent.global_path:
            path_from_root = parent.global_path + '/' + name
        elif parent:
            path_from_root = name
        bone = Bone(
            name,
            root.m_LocalPosition,
            root.m_LocalRotation,
            root.m_LocalScale,
            list(),
            path_from_root
        )
        bone_path_tbl[zlib.crc32(path_from_root.encode('utf-8'))] = bone
        if not parent:
            armature.root = bone
        else:
            parent.children.append(bone)
        for child in root.m_Children:
            dfs(child.read(), bone)
    dfs(root)
    armatures[armature.name] = armature
    assert armature.skinned_mesh_gameobject, "No SkinnedMeshRenderer attached to this Armature!"    
print('* Found static meshes:', len(static_mesh_gameobjects))
print('* Found armatures:', len(armatures))
def create_mesh(mesh_data: Mesh, skinned : bool):    
    mesh = bpy.data.meshes.new(name=mesh_data.name)
    obj = bpy.data.objects.new(mesh_data.name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    vtxFloats = int(len(mesh_data.m_Vertices) / mesh_data.m_VertexCount)
    normalFloats = int(len(mesh_data.m_Normals) / mesh_data.m_VertexCount)
    uvFloats = int(len(mesh_data.m_UV0) / mesh_data.m_VertexCount)
    # Bone Indices + Bone Weights
    deform_layer = None
    if skinned:        
        for boneHash in mesh_data.m_BoneNameHashes:            
            obj.vertex_groups.new(name=bone_path_tbl[boneHash].name)
        deform_layer = bm.verts.layers.deform.new()
    # Vertex position & vertex normal
    for vtx in range(0, mesh_data.m_VertexCount):        
        vert = bm.verts.new((
            -mesh_data.m_Vertices[vtx * vtxFloats], # x,y,z -> -x,z,y
            mesh_data.m_Vertices[vtx * vtxFloats + 2],
            mesh_data.m_Vertices[vtx * vtxFloats + 1]            
        ))
        vert.normal = (
            -mesh_data.m_Normals[vtx * normalFloats],
            mesh_data.m_Normals[vtx * normalFloats + 2],
            mesh_data.m_Normals[vtx * normalFloats + 1]
        )
        if deform_layer:
            for i in range(4):
                skin = mesh_data.m_Skin[vtx]
                vertex_group_index = skin.boneIndex[i]
                vert[deform_layer][vertex_group_index] = skin.weight[i]
    bm.verts.ensure_lookup_table()
    # Indices
    for idx in range(0, len(mesh_data.m_Indices), 3):
        face = bm.faces.new([bm.verts[mesh_data.m_Indices[idx + j]] for j in range(3)])
        face.smooth = True
    bm.to_mesh(mesh)
    bm.free()
    # UV
    uv_layer = mesh.uv_layers.new()
    mesh.uv_layers.active = uv_layer
    for face in mesh.polygons:
        for vtx, loop in zip(face.vertices, face.loop_indices):
            uv_layer.data[loop].uv = (
                mesh_data.m_UV0[vtx * uvFloats], 
                mesh_data.m_UV0[vtx * uvFloats + 1]
            )        

for mesh_go in static_mesh_gameobjects:
    mesh_rnd = mesh_go.m_MeshRenderer.read()
    mesh_data : Mesh = mesh_rnd.m_Mesh.read()
    create_mesh(mesh_data,False)    
    print('* Created Static Mesh', mesh_data.name)

for name, armature in armatures.items():
    mesh_rnd : Mesh = armature.skinned_mesh_gameobject.m_SkinnedMeshRenderer.read()
    mesh_data : Mesh = mesh_rnd.m_Mesh.read()
    create_mesh(mesh_data,True)
    print('* Created Armature', name, 'for Skinned Mesh', mesh_data.name)
