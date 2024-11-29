import copy
import math
import random
from compas.geometry import Box
from compas.geometry import Frame
from compas.geometry import Line
from compas.geometry import Point
from compas.geometry import Vector
from compas.datastructures import VolMesh


# The building grid class contains both data (attributes)
# of our grid and also its behavior (methods)
class BuildingGrid(object):
    def __init__(
        self, xsize, ysize, zsize, point, rotation, nx, ny, nz, selected_filter
    ):
        self.init_params = locals()
        self.ref_frame = Frame(point)
        self.ref_frame.rotate(rotation, point=point)
        self.volmesh = self.create_volmesh(
            selected_filter, xsize, ysize, zsize, point, rotation, nx, ny, nz
        )
        self.columns = []
        self.main_beams = []
        self.slabs = []
        self.walls = []
        self.internal_walls = []

    def generate_slabs(self, slab_height):
        # 1. Reset slabs list to an empty list
        self.slabs = []
        for face in self.volmesh.faces():
            normal = self.volmesh.face_normal(face)
            dot_product = normal.dot(Vector.Zaxis())
            if dot_product in (1, -1):
                # face is facing upwards or downwards, create a slab
                points = self.volmesh.face_points(face)
                # box = Box.from_corner_corner_height(points[0], points[2], slab_height)
                frame = Frame.from_points(points[0], points[1], points[2])
                # move the frame to the center of face
                frame.point = self.volmesh.face_centroid(face)
                frame.point.z -= slab_height / 2
                xsize = points[1].distance_to_point(points[0])
                ysize = points[2].distance_to_point(points[1])
                box = Box(xsize, ysize, slab_height, frame=frame)

                cell_id_opposite = self.volmesh.halfface_opposite_cell(face)
                if cell_id_opposite is None:
                    if dot_product == 1:  # bottom face
                        slab = Slab(box, face, "bottom_slab")
                    else:  # top face
                        slab = Slab(box, face, "roof")
                else:
                    slab = Slab(box, face, "floor_slab")

                self.slabs.append(slab)

    def generate_facades(self, thickness, skipped_faces=[], external=True):
        # 1. Reset the list of walls and assign facade_thickness to an attribute
        # ... your code here ...
        if external:
            self.walls = []
        else:
            self.internal_walls = []

        for face in self.volmesh.halffaces():
            if face in skipped_faces:
                continue
            if external and self.volmesh.is_halfface_on_boundary(face):
                wall = self.generate_wall_from_face(face, thickness, "facade")
                if wall:
                    self.walls.append(wall)
            elif not external and not self.volmesh.is_halfface_on_boundary(face):
                wall = self.generate_wall_from_face(face, thickness, "internal_wall")
                if wall:
                    self.internal_walls.append(wall)

    def generate_wall_from_face(self, face, thickness, category):
        face_normal = self.volmesh.halfface_normal(face)

        if abs(face_normal.dot(Vector.Zaxis())) < 1e-5:

            face_points = self.volmesh.face_points(face)
            face_centroid = self.volmesh.face_centroid(face)
            frame = copy.deepcopy(self.ref_frame)
            frame.point = face_centroid

            height = abs(face_points[0].z - face_centroid.z) * 2
            p0, p1 = Balcony.get_halfface_lower_two_points(face, self.volmesh)
            width = p0.distance_to_point(p1)
            if abs(face_normal.dot(frame.yaxis)) < 1e-5:
                box = Box(thickness, width, height, frame=frame)
            else:
                box = Box(width, thickness, height, frame=frame)

            wall = Wall(box, face, category)
            return wall
        else:
            return None

    # Generate columns and append them to the self.columns attribute
    def generate_columns(self, column_width_x, column_depth_y):
        self.column_width_x = column_width_x
        self.column_depth_y = column_depth_y

        # First reset the list of columns
        self.columns = []

        # Now generate columns
        for uv in self.volmesh.edges():
            # If the edge vector is parallel to unit vector Z...
            edge_vector = self.volmesh.edge_direction(uv)

            if (
                edge_vector.dot(Vector.Zaxis()) == 1
            ):  # edge vector is always pointing upwards if it's vertical
                # ...we add a column
                edge_midpoint = self.volmesh.edge_point(uv)
                edge_length = self.volmesh.edge_length(uv)
                frame = copy.deepcopy(self.ref_frame)
                frame.point = edge_midpoint

                box = Box(column_width_x, column_depth_y, edge_length, frame=frame)

                column = Column(box, uv, "building_column")
                self.columns.append(column)

    # This method is provided as is
    # It shows how to create main beams
    # Main beams are a nbit more complicated than columns
    # because they need to be adjusted in length to match the column
    def generate_main_beams(self, main_beam_width, main_beam_height):
        # First reset the list of main beams
        self.main_beams = []

        for uv in self.volmesh.edges():
            edge_vector = self.volmesh.edge_direction(uv)

            if edge_vector.dot(Vector.Zaxis()) == 0:

                start, end = self.volmesh.edge_coordinates(uv)
                line = Line(start, end)

                # Shorten the beam to fit the columns
                if edge_vector.dot(Vector.Xaxis()) in (1, -1):
                    shift_value = self.column_width_x
                else:
                    shift_value = self.column_depth_y

                # Create the box in the origin of world XY frame
                box = Box.from_width_height_depth(
                    main_beam_width, main_beam_height, line.length - shift_value
                )
                # frame = Frame(
                #     line.midpoint, edge_vector.cross(Vector.Zaxis()), edge_vector
                # )
                frame = copy.deepcopy(self.ref_frame)
                frame.xaxis = edge_vector.cross(Vector.Zaxis())
                frame.y_axis = edge_vector
                frame.point = line.midpoint
                frame.point.z -= main_beam_height / 2

                # Move box to correct frame
                box.frame = frame

                mainbeam = MainBeam(box, uv)
                self.main_beams.append(mainbeam)

    def create_volmesh(
        self, selected_filter, xsize, ysize, zsize, point, rotation, nx, ny, nz
    ):
        volmesh = VolMesh()
        vertex_keys = dict()
        x0 = point.x
        y0 = point.y
        z0 = point.z

        for ix in range(nx):
            for iy in range(ny):
                for iz in range(nz):
                    corner_1 = Point(ix * xsize + x0, iy * ysize + y0, iz * zsize + z0)
                    corner_2 = Point(corner_1.x + xsize, corner_1.y + ysize, corner_1.z)
                    #                    corner_1.rotate(rotation, point=point)
                    #                    corner_2.rotate(rotation, point=point)
                    box = Box.from_corner_corner_height(corner_1, corner_2, zsize)
                    box.rotate(rotation, point=point)
                    # Only add cell if within filter
                    if selected_filter.is_included(box.corner(0), ix, iy, iz):
                        #                        box = Box.from_corner_corner_height(corner_1, corner_2, zsize)
                        #                        box.rotate(rotation, point=point)
                        corner_points = box.compute_vertices()
                        vertices = []

                        for v in corner_points:
                            gkey = str(v)
                            if gkey not in vertex_keys:
                                vertex_keys[gkey] = volmesh.add_vertex(
                                    x=v[0], y=v[1], z=v[2]
                                )

                            vertex = vertex_keys[gkey]
                            vertices.append(vertex)

                        a, b, c, d, e, f, g, h = vertices
                        faces = [
                            [a, d, c, b],  # bottom face
                            [a, e, f, d],  # front face
                            [a, b, h, e],  # left face
                            [b, c, g, h],  # back face
                            [d, f, g, c],  # right face
                            [e, h, g, f],  # top face
                        ]

                        # Add the cell with the defined faces
                        volmesh.add_cell(faces, attr_dict=dict(ix=ix, iy=iy, iz=iz))

        return volmesh

    def get_exposed_faces(self, vertical=True, horizontal=False):
        """
        Get the indices of the exposed faces of the building (volmesh).

        :param vertical: if vertical exposed surfaces should be included, defaults to True
        :type vertical: bool, optional
        :param horizontal: if horizontal exposed surfaces should be included, defaults to False
        :type horizontal: bool, optional
        :return: list of exposed face indices
        :rtype: list of int
        """
        exposed_face_indices = []
        for face in self.volmesh.faces():
            if self.volmesh.is_halfface_on_boundary(face):
                normal = self.volmesh.halfface_normal(face)
                if vertical and normal.dot(Vector.Zaxis()) == 0:
                    exposed_face_indices.append(face)
                if horizontal and normal.dot(Vector.Zaxis()) in (1, -1):
                    exposed_face_indices.append(face)
        return exposed_face_indices

    def add_balcony(self, halfface_idx, length, height):
        balcony = Balcony(length, height, halfface_idx, self.volmesh)
        self.slabs.extend(balcony.slabs)
        self.main_beams.extend(balcony.beams)
        self.columns.extend(balcony.columns)

    def generate_balconies(self, min_length, max_length, height, n_balconies, **kwargs):
        """
        randomly generate n balconies on the exposed faces of the building (volmesh).
        The cantiliver length of the balcony decreases with the height of the building.

        :param min_length: minimal length of the cantiliver of the balcony
        :type min_length: float
        :param max_length: maximal length of the cantiliver of the balcony
        :type max_length: float
        :param height: _description_
        :type height: _type_
        :param n_balconies: _description_
        :type n_balconies: _type_

        :return: list of indices of the faces where balconies are added
        :rtype: list of int
        """
        exposed_faces = self.get_exposed_faces(vertical=True, horizontal=False)
        # randomly choosing n_balconies faces from the exposed faces without repetition
        n_exposed_faces = len(exposed_faces)
        n_balconies = min(n_balconies, n_exposed_faces)
        selected_faces = random.sample(exposed_faces, n_balconies)
        # get the height of the building
        building_height = self.init_params["zsize"] * (self.init_params["nz"] + 1)
        for face in selected_faces:
            # get the centroid of face to understand the height of balcony
            centroid = self.volmesh.halfface_centroid(face)
            # the higher the balcony, the smaller the length. But minimal length is 1
            length = min_length + max(
                0, (max_length - min_length) * (centroid.z / building_height)
            )
            self.add_balcony(face, length, height, **kwargs)
        return selected_faces

    def number_of_columns(self):
        return len(self.columns)

    def number_of_main_beams(self):
        return len(self.main_beams)

    def calculate_volume(self, element, category):
        volume = 0
        if element == "column":
            for column in self.columns:
                if category is None or column.category == category:
                    volume += column.geometry.volume
        elif element == "beam":
            for beam in self.main_beams:
                if category is None or beam.category == category:
                    volume += beam.geometry.volume
        elif element == "slab":
            for slab in self.slabs:
                if category is None or slab.category == category:
                    volume += slab.geometry.volume
        elif element == "wall":
            for wall in self.walls:
                if category is None or wall.category == category:
                    volume += wall.geometry.volume
        return volume


if __name__ == "__main__":
    pass
