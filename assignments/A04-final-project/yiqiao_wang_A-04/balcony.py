from compas.geometry import Box
from compas.geometry import Frame
from compas.geometry import Vector, Translation
import copy


class Balcony(object):
    def __init__(
        self,
        length,
        height,
        halfface_idx,
        volmesh,
        slab_thickness=0.1,
        beam_width=0.1,
        beam_height=0.2,
        column_length=0.1,
        column_width=0.1,
        handrail_width=0.05,
        handrail_height=0.1,
    ):
        """
        Create a balcony that is attached to an exposed halfface of a volmesh.

        The balcony recognizes a naked vertical halfface, and extrude a cube (Volmesh) from it to the outside.
        It contains:
        - a floor slab on the bottom,
        - two columns on the outside of the balcony,
        - three beams on the bottom and three handrails on the top.

        If the viewer is facing the facade from outside of the building,
        the lower left corner of the facade is p0 (self.points[0]), the lower right corner of the facade is p1.
        Then p2 and p3 are upper right and upper left corners of the facade, forming an anticlockwise order.
        p0 to p3 are all points on the halfface/facade.

        p4 is on the same location as p0, but it's the point that is extruded to the outside of the building.
        following the same anti-clockwise order, p5, p6, p7 is defined. Same order is applied to the frames.

        :param length: length of the cantiliver of the balcony
        :type length: float
        :param height: height of the handrail of the balcony, relative to the floor slab.
        :type height: float
        :param halfface_idx: index of the halfface that the balcony is attached to.
        Used to locate the halfface on the volmesh
        :type halfface_idx: int
        :param volmesh: a volmesh of the building, where the halfface belongs to
        :type volmesh: compas.datastructures.VolMesh
        :raises ValueError: if halfface is not exposed, the surface is not an external surface, so no balcony can be created
        :raises ValueError: if the halfface is not vertical, the surface is not a wall, so no balcony can be created
        """
        # check if the halfface is naked
        if not volmesh.is_halfface_on_boundary(halfface_idx):
            raise ValueError("The halfface is not naked.")

        # check if halfface normal is horizontal
        normal = volmesh.halfface_normal(halfface_idx).inverted()
        if normal.dot(Vector.Zaxis()) != 0:
            raise ValueError("The halfface is not vertical, no balcony can be created.")

        self.main_volmesh = volmesh
        self.attached_halfface_idx = halfface_idx

        p0, p1 = self.get_halfface_lower_two_points(
            self.attached_halfface_idx, self.main_volmesh
        )
        width = p0.distance_to_point(p1)
        vx = normal.unitized() * length / 2
        vy = Vector.from_start_end(p0, p1).unitized() * width / 2
        vz = Vector.Zaxis() * height / 2

        points = self.get_balcony_points(p0, p1, length, height)
        frame0 = Frame(points[0], vx, vy)
        frames = []
        for point in points:
            frame = copy.deepcopy(frame0)
            frame.point = point
            frames.append(frame)
        beam_04 = MainBeam(
            Box(length, beam_width, beam_height, frames[0]).translated(vx),
            None,
            "balcony_beam",
        )
        beam_15 = MainBeam(
            Box(length, beam_width, beam_height, frames[1]).translated(vx),
            None,
            "balcony_beam",
        )
        beam_45 = MainBeam(
            Box(beam_width, width, beam_height, frames[4]).translated(vy),
            None,
            "balcony_beam",
        )
        # slab will be formed on the bottom of the balcony
        slab = Slab(
            Box(length, width, zsize=slab_thickness, frame=frames[0]).translated(
                vx + vy
            ),
            None,
            "balcony_slab",
        )
        #        slab.translation(
        # handrail will be formed on the top of the balcony
        handrail_37 = MainBeam(
            Box(length, handrail_width, handrail_height, frames[3]).translated(vx),
            None,
            "balcony_handrail",
        )
        handrail_26 = MainBeam(
            Box(length, handrail_width, handrail_height, frames[2]).translated(vx),
            None,
            "balcony_handrail",
        )
        handrail_76 = MainBeam(
            Box(handrail_width, width, handrail_height, frames[7]).translated(vy),
            None,
            "balcony_handrail",
        )

        column_47 = Column(
            Box(column_length, column_width, height, frames[4]), None, "balcony_column"
        )
        column_47.geometry.frame.point.z += height / 2
        column_56 = Column(
            Box(column_length, column_width, height, frames[5]), None, "balcony_column"
        )
        column_56.geometry.frame.point.z += height / 2

        self.beams = [beam_04, beam_15, beam_45, handrail_37, handrail_26, handrail_76]
        self.columns = [column_47, column_56]
        self.slabs = [slab]
        self.points = points
        self.frames = frames

    @staticmethod
    def get_halfface_lower_two_points(halfface_idx, volmesh):
        """
        The function identifies the outside of halfface, and returns a tuple of two points, p0 and p1. This can be used to
        locate the balcony on the facade.

        :return: return the lower left and lower right points of the halfface
        :rtype: tuple of Point
        """
        # check if halfface is vertical
        normal = volmesh.halfface_normal(halfface_idx).inverted()

        points = volmesh.face_points(halfface_idx)
        # find the two points with the lowest z value
        lower_points = []
        for point in points:
            if len(lower_points) < 2:
                lower_points.append(point)
            else:
                if point.z < lower_points[0].z:
                    lower_points[0] = point
                elif point.z < lower_points[1].z:
                    lower_points[1] = point

        # also make sure that the normal of the halfface cross product with the vector of the two points is pointing upwards
        # so that (normal, (points[0] -> points[1]), Zaxis) is a right-hand coordinate system
        if normal.cross(lower_points[1] - lower_points[0]).dot(Vector.Zaxis()) < 0:
            lower_points[0], lower_points[1] = lower_points[1], lower_points[0]

        return lower_points[0], lower_points[1]

    def get_balcony_points(self, p0, p1, length, height):
        """
        Calculate the points of a balcony given two initial points, length, and height.

        :param p0: The starting point of the balcony (lower left corner).
        :type p0: Point
        :param p1: The ending point of the balcony (lower right corner).
        :type p1: Point
        :param length: The length of the cantilever of the balcony.
        :type length: float
        :param height: The height of the balcony.
        :type height: float
        :return: A list of 8 points representing the balcony.
        :rtype: list of Point
        """

        vy = Vector.from_start_end(p0, p1)
        vx = vy.cross(Vector.Zaxis()).unitized()
        t_x = Translation.from_vector(vx * length)
        t_z = Translation.from_vector(Vector.Zaxis() * height)
        p2 = p1.transformed(t_z)
        p3 = p0.transformed(t_z)
        p4 = p0.transformed(t_x)
        p5 = p1.transformed(t_x)
        p6 = p2.transformed(t_x)
        p7 = p3.transformed(t_x)
        return [p0, p1, p2, p3, p4, p5, p6, p7]

    def number_of_columns(self):
        return len(self.columns)

    def number_of_main_beams(self):
        return len(self.main_beams)

    def calculate_volume(self):
        pass


if __name__ == "__main__":
    pass
