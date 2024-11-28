from compas.geometry import Box
from compas.geometry import Frame
from compas.geometry import Line
from compas.geometry import Point
from compas.geometry import Vector
from compas.datastructures import VolMesh
from balcony import Balcony


# The building grid class contains both data (attributes)
# of our grid and also its behavior (methods)
class BuildingGrid(object):
    def __init__(
        self, xsize, ysize, zsize, point, rotation, nx, ny, nz, selected_filter
    ):
        self.volmesh = self.create_volmesh(
            selected_filter, xsize, ysize, zsize, point, rotation, nx, ny, nz
        )
        self.columns = []
        self.main_beams = []
        self.slabs = []

    def generate_slabs(self, slab_height):
        # 1. Reset slabs list to an empty list
        self.slabs = []
        for face in self.volmesh.faces():
            normal = self.volmesh.face_normal(face)
            dot_product = normal.dot(Vector.Zaxis())
            if dot_product in (1, -1):
                # face is facing upwards or downwards, create a slab
                centroid = self.volmesh.halfface_centroid(face)
                points = self.volmesh.face_points(face)
                box = Box.from_corner_corner_height(points[0], points[2], slab_height)

                # 8. Create an instance of the slab class you created above
                # ... your code here ...
                slab = Slab(box, face)

                # 9. Append it to the grid.slabs attribute list
                # ... your code here ...
                self.slabs.append(slab)

    # END OF MAIN TASK

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

            if edge_vector.dot(Vector.Zaxis()) in (1, -1):
                # ...we add a column
                edge_midpoint = self.volmesh.edge_point(uv)
                edge_length = self.volmesh.edge_length(uv)

                box = Box(column_width_x, column_depth_y, edge_length)
                box.frame.point = edge_midpoint

                column = Column(box, uv)
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
                frame = Frame(
                    line.midpoint, edge_vector.cross(Vector.Zaxis()), edge_vector
                )
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

    def get_exposed_faces(self):
        exposed_face_indices = []
        for face in self.volmesh.faces():
            if self.volmesh.is_halfface_on_boundary(face):
                exposed_face_indices.append(face)
        return exposed_face_indices
        # pass

    def number_of_columns(self):
        return len(self.columns)

    def number_of_main_beams(self):
        return len(self.main_beams)

    def calculate_volume(self):
        pass


if __name__ == "__main__":
    pass


# Create the Slab class here
class Slab(object):
    def __init__(self, geometry, halfface, category=None):
        self.geometry = geometry
        self.halfface = halfface
        self.category = category


class Column(object):
    def __init__(self, geometry, edge):
        self.geometry = geometry
        self.edge = edge


class MainBeam(object):
    def __init__(self, geometry, edge):
        self.geometry = geometry
        self.edge = edge
