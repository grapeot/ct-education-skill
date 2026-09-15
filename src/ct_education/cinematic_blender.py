"""Deterministic Blender entry point, copied into each external cinematic run.

Execute with Blender's Python, not the application environment. Runtime state and
packed assets are private. Re-running this exact script/state resumes missing PNGs.
"""

import json
import math
from pathlib import Path
import sys
import time

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Quaternion, Vector


def main():
    root = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
    config = json.loads((root / 'state.json').read_text())
    center = Vector(config['center_ras'])
    def world(point):
        return (Vector(point) - center) * 0.001

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = config['width'] // 2 - 36
    scene.render.resolution_y = config['height'] - 180
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.film_transparent = False
    scene.render.fps = config['fps']
    scene.render.use_motion_blur = False
    scene.world.color = (0.025, 0.035, 0.05)
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (0.0034, 0.0056, 0.011, 1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = 1
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    if hasattr(scene, 'eevee') and hasattr(scene.eevee, 'taa_render_samples'):
        scene.eevee.taa_render_samples = config['samples']
    scene['center_ras_mm'] = list(center)
    scene['ras_to_blender_scale'] = 0.001
    scene['source_contract'] = 'HU plane is source evidence; meshes and footprint are display derivatives.'

    camera_data = bpy.data.cameras.new('Film camera')
    camera = bpy.data.objects.new('Film camera', camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera_data.lens = 48
    camera_data.sensor_width = 36
    camera_data.sensor_fit = 'HORIZONTAL'
    camera_data.clip_start = 0.001
    camera_data.clip_end = 100
    for name, position, power, color in [
        ('Soft key', (0.5, -0.5, 0.8), 7, (0.82, 0.91, 1)),
        ('Warm rim', (-0.5, 0.3, 0.5), 4, (1, 0.79, 0.55)),
        ('Fill', (0.2, 0.5, -0.2), 4, (0.6, 0.85, 1)),
    ]:
        light = bpy.data.lights.new(name, 'AREA')
        light.energy, light.color, light.shape, light.size = power, color, 'DISK', 0.65
        obj = bpy.data.objects.new(name, light)
        scene.collection.objects.link(obj)
        obj.location = position
        obj.rotation_euler = (-obj.location).to_track_quat('-Z', 'Y').to_euler()

    colors = config['colors']
    objects, controls = {}, {}
    mesh_radius = 0.0
    for layer in config['layers']:
        data = json.loads((root / 'meshes' / f'{layer}.json').read_text())
        xyz, indices = data['positions'], data['indices']
        vertices = [world(xyz[i:i + 3]) for i in range(0, len(xyz), 3)]
        mesh_radius = max(mesh_radius, max((v.length for v in vertices), default=0))
        mesh = bpy.data.meshes.new(layer)
        mesh.from_pydata(vertices, [], [indices[i:i + 3] for i in range(0, len(indices), 3)])
        mesh.update()
        obj = bpy.data.objects.new(layer, mesh)
        scene.collection.objects.link(obj)
        for polygon in mesh.polygons:
            polygon.use_smooth = True
        mat = bpy.data.materials.new(layer + ' / candidate surface')
        mat.use_nodes = True
        mat.surface_render_method = 'BLENDED'
        mat.use_transparency_overlap = False
        nodes, links = mat.node_tree.nodes, mat.node_tree.links
        nodes.clear()
        out = nodes.new('ShaderNodeOutputMaterial')
        solid = nodes.new('ShaderNodeBsdfPrincipled')
        solid.inputs['Base Color'].default_value = colors.get(layer, (0.5, 0.5, 0.5, 1))
        solid.inputs['Roughness'].default_value = 0.57
        transparent = nodes.new('ShaderNodeBsdfTransparent')
        mix = nodes.new('ShaderNodeMixShader')
        links.new(transparent.outputs[0], mix.inputs[1])
        links.new(solid.outputs[0], mix.inputs[2])
        links.new(mix.outputs[0], out.inputs[0])
        geo = nodes.new('ShaderNodeNewGeometry')
        dot = nodes.new('ShaderNodeVectorMath')
        dot.operation = 'DOT_PRODUCT'
        links.new(geo.outputs['Position'], dot.inputs[0])
        compare = nodes.new('ShaderNodeMath')
        compare.operation = 'LESS_THAN'
        links.new(dot.outputs['Value'], compare.inputs[0])
        opacity = nodes.new('ShaderNodeMath')
        opacity.operation = 'MULTIPLY'
        links.new(compare.outputs[0], opacity.inputs[0])
        links.new(opacity.outputs[0], mix.inputs[0])
        obj.data.materials.append(mat)
        objects[layer], controls[layer] = obj, (dot, compare, opacity, solid)

    def plane_object(name):
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata([(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)], [], [(0, 1, 2, 3)])
        uv = mesh.uv_layers.new()
        for loop, value in zip(uv.data, [(0, 0), (1, 0), (1, 1), (0, 1)]):
            loop.uv = value
        obj = bpy.data.objects.new(name, mesh)
        scene.collection.objects.link(obj)
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        mat.surface_render_method = 'DITHERED'
        nodes, links = mat.node_tree.nodes, mat.node_tree.links
        nodes.clear()
        out = nodes.new('ShaderNodeOutputMaterial')
        texture = nodes.new('ShaderNodeTexImage')
        texture.interpolation = 'Linear'
        emit = nodes.new('ShaderNodeEmission')
        links.new(texture.outputs['Color'], emit.inputs['Color'])
        trans = nodes.new('ShaderNodeBsdfTransparent')
        mix = nodes.new('ShaderNodeMixShader')
        opacity = nodes.new('ShaderNodeMath')
        opacity.operation = 'MULTIPLY'
        opacity.inputs[1].default_value = 1
        links.new(texture.outputs['Alpha'], opacity.inputs[0])
        links.new(opacity.outputs[0], mix.inputs[0])
        links.new(trans.outputs[0], mix.inputs[1])
        links.new(emit.outputs[0], mix.inputs[2])
        links.new(mix.outputs[0], out.inputs[0])
        obj.data.materials.append(mat)
        return obj, texture, opacity

    def update_plane(obj, texture, state, image):
        u, v, n = (Vector(state[key]) for key in ('u', 'v', 'normal'))
        obj.location = world(state['center_ras'])
        obj.rotation_euler = Matrix((u, v, n)).transposed().to_euler()
        obj.scale = (state['size_mm'][0] * 0.0005, state['size_mm'][1] * 0.0005, 1)
        texture.image = bpy.data.images.load(str(root / image), check_existing=True)
        texture.image.colorspace_settings.name = 'sRGB'

    plane_obj, plane_texture, plane_opacity = plane_object('Native HU image plane')
    stack = []
    for item in config['stack']:
        obj, texture, opacity = plane_object('Representative subset plane')
        obj.data.materials[0].surface_render_method = 'BLENDED'
        update_plane(obj, texture, item['plane'], item['image'])
        stack.append((obj, obj.location.copy(), opacity))

    marker_curve = bpy.data.curves.new('Locator ring / not a lesion boundary', 'CURVE')
    marker_curve.dimensions = '3D'
    marker_curve.bevel_depth = 0.00035
    marker_curve.bevel_resolution = 2
    marker_spline = marker_curve.splines.new('POLY')
    marker_spline.points.add(63)
    marker_spline.use_cyclic_u = True
    marker_obj = bpy.data.objects.new('Locator ring / supplied radius only', marker_curve)
    scene.collection.objects.link(marker_obj)
    marker_material = bpy.data.materials.new('Locator amber')
    marker_material.use_nodes = True
    marker_material.surface_render_method = 'DITHERED'
    nodes, links = marker_material.node_tree.nodes, marker_material.node_tree.links
    nodes.clear()
    out = nodes.new('ShaderNodeOutputMaterial')
    emission = nodes.new('ShaderNodeEmission')
    emission.inputs['Color'].default_value = (1, 0.55, 0.12, 1)
    transparent = nodes.new('ShaderNodeBsdfTransparent')
    marker_mix = nodes.new('ShaderNodeMixShader')
    links.new(transparent.outputs[0], marker_mix.inputs[1])
    links.new(emission.outputs[0], marker_mix.inputs[2])
    links.new(marker_mix.outputs[0], out.inputs[0])
    marker_curve.materials.append(marker_material)
    bpy.context.view_layer.update()
    local = config['candidate_geometry']
    local_planes = []
    local_surface = None
    local_box = None
    if local:
        for item in local['planes']:
            obj, texture, opacity = plane_object('Local native HU / ' + item['plane']['axis'])
            obj.data.materials[0].surface_render_method = 'BLENDED'
            update_plane(obj, texture, item['plane'], item['image'])
            local_planes.append((obj, opacity))
        surface_path = local['density_mesh'] or local['mesh']
        if surface_path:
            data = json.loads((root / surface_path).read_text())
            xyz, indices = data['positions'], data['indices']
            mesh = bpy.data.meshes.new('Exploratory CT isodensity / boundary unverified')
            mesh.from_pydata([world(xyz[j:j + 3]) for j in range(0, len(xyz), 3)], [],
                             [indices[j:j + 3] for j in range(0, len(indices), 3)])
            mesh.update()
            local_surface = bpy.data.objects.new(mesh.name, mesh)
            scene.collection.objects.link(local_surface)
            local_surface['representation_type'] = local['density_display']['representation_type']
            local_surface['threshold_hu'] = local['density_display']['threshold_hu']
            local_surface['verified_nodule_boundary'] = False
            local_surface['strict_boundary_status'] = local['status']
            material = bpy.data.materials.new('Candidate violet / educational color')
            material.use_nodes = True
            material.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.48, 0.25, 0.7, 1)
            material.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.38
            mesh.materials.append(material)
            for polygon in mesh.polygons:
                polygon.use_smooth = True
        else:
            curve = bpy.data.curves.new('Localized region box / not a segmented surface', 'CURVE')
            curve.dimensions, curve.bevel_depth = '3D', 0.00005
            curve.bevel_resolution = 1
            half = local['locator_half_mm'] * 0.001
            origin_local = world(local['center_ras'])
            corners = [origin_local + Vector((x * half, y * half, z * half))
                       for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
            for a in range(8):
                for b in range(a + 1, 8):
                    if (a ^ b) in (1, 2, 4):
                        spline = curve.splines.new('POLY')
                        spline.points.add(1)
                        spline.points[0].co = (*corners[a], 1)
                        spline.points[1].co = (*corners[b], 1)
            curve.materials.append(marker_material)
            local_box = bpy.data.objects.new(curve.name, curve)
            scene.collection.objects.link(local_box)
        emission.inputs['Color'].default_value = (0.65, 0.38, 1, 1)

    timings = []
    for i, state in enumerate(config['frames']):
        began = time.monotonic()
        plane = state['plane']
        update_plane(plane_obj, plane_texture, plane, state['image'])
        plane_obj.hide_render = not state['show_plane']
        plane_opacity.inputs[1].default_value = state['plane_opacity']
        for j, (obj, opacity) in enumerate(local_planes):
            obj.hide_render = not state['depth_view']
            opacity.inputs[1].default_value = (0.07 if j == 0 else 0.045) if local_surface else (1.0 if j == 0 else 0.32)
        if local_surface:
            local_surface.hide_render = not state['depth_view']
        if local_box:
            local_box.hide_render = not state['depth_view']
        plane_obj.data.materials[0].surface_render_method = 'BLENDED' if state['depth_view'] else 'DITHERED'
        for j, (obj, rest, opacity) in enumerate(stack):
            entry = state['stack_entries'][j]
            # The middle plane is the shared primary image, not a duplicate surface.
            obj.hide_render = j == 3 or entry <= 0 or state['stack_opacity'] <= 0
            opacity.inputs[1].default_value = entry * state['stack_opacity']
            offset = Vector((0.025 * (1 - entry), 0, (j - 3) * 0.018 * state['stack']))
            obj.location = rest + offset if state['stack_opacity'] > 0 else rest
        normal = Vector(plane['normal'])
        origin = world(plane['center_ras'])
        for layer, obj in objects.items():
            alpha = state['visibility'].get(layer, 0)
            obj.hide_render = alpha <= 0
            dot, compare, opacity, solid = controls[layer]
            dot.inputs[1].default_value = normal
            compare.inputs[1].default_value = normal.dot(origin) if state['clip'] else 100
            opacity.inputs[1].default_value = alpha
            if layer in ('airways', 'vessels'):
                solid.inputs['Emission Color'].default_value = colors[layer]
                solid.inputs['Emission Strength'].default_value = 0.04 + 0.45 * state['branch_emphasis']
            if layer == 'lungs':
                material = obj.data.materials[0]
                material.surface_render_method = 'BLENDED'
                material.use_transparency_overlap = state['depth_view']
        u, v = Vector(plane['u']), Vector(plane['v'])
        face_basis = Matrix((u, v, normal)).transposed().to_quaternion()
        angle = state['orbit']
        # The calm 130-155 degree arc faces anteriorly without rotating patient axes.
        azimuth = angle + math.radians(38)
        direction = Vector((math.sin(azimuth), -math.cos(azimuth), state['camera_elevation'])).normalized()
        overview = (-direction).to_track_quat('-Z', 'Y')
        rotation = overview.slerp(face_basis, state['face'])
        aspect = scene.render.resolution_x / scene.render.resolution_y
        plane_width = max(plane['size_mm'][0], plane['size_mm'][1] * aspect) * 0.001 / 0.86
        overview_width = 2 * mesh_radius * max(1, aspect) / 0.88
        field_width = plane_width * state['face'] + max(plane_width, overview_width) * (1 - state['face'])
        field_width *= 1 + 0.2 * state['stack_framing']
        field_width += 0.5 * overview_width * math.sin(math.pi * state['face'])**2
        target = origin * state['face']
        depth_base_width = None
        if state['depth_view']:
            # Orbit the supplied patient point, never an airway or whole-volume center.
            progress = state['outro_progress']
            initial_rotation = face_basis @ Quaternion((1, 0, 0), math.radians(25)) @ Quaternion((0, 1, 0), math.radians(-25))
            final_rotation = face_basis @ Quaternion((1, 0, 0), math.radians(25)) @ Quaternion((0, 1, 0), math.radians(25))
            rotation = initial_rotation.slerp(final_rotation, progress)
            candidate_target = world(state['locator']['position_ras']) if state['locator'] else origin
            target = candidate_target
            depth_base_width = 0.1 * max(1, aspect)
            field_width = depth_base_width * state['inspection_scale']
        distance = field_width * camera_data.lens / camera_data.sensor_width
        camera.rotation_mode = 'QUATERNION'
        camera.rotation_quaternion = rotation
        camera.location = target + rotation @ Vector((0, 0, distance))
        camera_data.type = 'ORTHO' if state['face'] == 1 or state['depth_view'] else 'PERSP'
        camera_data.ortho_scale = field_width
        marker_obj.hide_render = True
        marker_mix.inputs[0].default_value = state['marker_opacity']
        if state['locator']:
            marker_center = world(state['locator']['position_ras'])
            radius = state['locator']['radius_mm'] * 0.001
            for j, point in enumerate(marker_spline.points):
                angle = 2 * math.pi * j / len(marker_spline.points)
                point.co = (*(marker_center + radius * (u * math.cos(angle) + v * math.sin(angle))), 1)
        bpy.context.view_layer.update()
        # A true RAS-mm segment is projected anew, never assigned a fixed pixel length.
        anchor = origin - u * plane['size_mm'][0] * 0.0004 - v * plane['size_mm'][1] * 0.00035
        camera_right = rotation @ Vector((1, 0, 0))
        ruler_direction = camera_right - normal * camera_right.dot(normal)
        ruler_direction = ruler_direction.normalized() if ruler_direction.length > 1e-6 else u
        endpoint = anchor + ruler_direction * state['ruler_mm'] * 0.001
        def project(point):
            p = world_to_camera_view(scene, camera, point)
            return [p.x * scene.render.resolution_x, (1 - p.y) * scene.render.resolution_y]
        metadata = dict(ruler_pixels=[project(anchor), project(endpoint)], camera_matrix=[list(row) for row in camera.matrix_world],
                        projection=camera_data.type, field_width_m=field_width,
                        camera_right=list(rotation @ Vector((1, 0, 0))), camera_up=list(rotation @ Vector((0, 1, 0))))
        metadata['orientation_pixels'] = [project(origin - u * plane['size_mm'][0] * 0.00045),
                                          project(origin + u * plane['size_mm'][0] * 0.00042),
                                          project(origin + v * plane['size_mm'][1] * 0.00045)]
        metadata['locator_pixels'] = project(world(state['locator']['position_ras'])) if state['locator'] else None
        metadata['ruler_endpoints_ras'] = [list(anchor * 1000 + center), list(endpoint * 1000 + center)]
        metadata['stack_entries'] = state['stack_entries']
        metadata['stack_world_offsets_m'] = [list(obj.location - rest) for obj, rest, opacity in stack]
        metadata['branch_emphasis'] = state['branch_emphasis']
        metadata['camera_target_ras'] = list(target * 1000 + center)
        metadata['depth_base_width_m'] = depth_base_width
        metadata['locator_ring_center_ras'] = state['locator']['position_ras'] if not marker_obj.hide_render else None
        metadata['locator_ring_radius_mm'] = state['locator']['radius_mm'] if not marker_obj.hide_render else None
        metadata['visible_layers'] = [layer for layer, obj in objects.items() if not obj.hide_render]
        metadata['candidate_mode'] = local['status'] if local and state['depth_view'] else None
        metadata['local_plane_count'] = sum(not obj.hide_render for obj, opacity in local_planes)
        metadata['density_surface_visible'] = bool(local_surface and not local_surface.hide_render)
        metadata['density_display'] = local['density_display'] if local and state['depth_view'] else None
        if local_surface and state['depth_view']:
            projected = [project(Vector(p)) for p in local_surface.bound_box]
            metadata['density_surface_bounds_pixels'] = [[min(p[axis] for p in projected), max(p[axis] for p in projected)] for axis in (0, 1)]
        (root / 'left' / f'{i:05d}.json').write_text(json.dumps(metadata))
        if i == 0:
            for image in bpy.data.images:
                if image.source == 'FILE':
                    image.pack()
            bpy.ops.wm.save_as_mainfile(filepath=str(root / 'master.blend'))
        destination = root / 'left' / f'{i:05d}.png'
        if not destination.exists():
            scene.render.filepath = str(destination)
            bpy.ops.render.render(write_still=True)
        timings.append(time.monotonic() - began)
        # Avoid retaining a new full-size texture for every frame of a long film.
        current = plane_texture.image
        for image in list(bpy.data.images):
            if image != current and image.users == 0:
                bpy.data.images.remove(image)
    (root / 'benchmark.json').write_text(json.dumps(dict(frame_seconds=timings, total_seconds=sum(timings))))


if __name__ == '__main__':
    main()
