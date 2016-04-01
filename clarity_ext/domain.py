
class Analyte:
    """
    Describes an Analyte in the Clarity LIMS system, including custom UDFs.

    Takes an analyte resource as input.
    """

    def __init__(self, resource):
        self.resource = resource

    # Mapped properties from the underlying resource
    # TODO: we might want to supply all of these via inheritance (or some Python trick)
    # or require the caller to use the underlying resource object (but that increases complexity)
    @property
    def name(self):
        return self.resource.name

    # Mapped UDFs
    @property
    def concentration(self):
        return self.resource.udf["Concentration"]

    @property
    def target_concentration(self):
        return float(self.resource.udf["Target Concentration"])

    @property
    def target_volume(self):
        return self.resource.udf["Target Volume"]

    # Other properties
    @property
    def well(self):
        row, col = self.resource.location[1].split(":")
        return Well(row, col)

    @property
    def container(self):
        return self.resource.location[0]

    @property
    def sample(self):
        return self.resource.samples[0]


class Well:
    """Encapsulates a well in a plate"""
    def __init__(self, row, col, artifact_name=None, artifact_id=None):
        self.row = row
        self.col = col
        self.artifact_name = artifact_name
        self.row_index_dict = dict(
            [(row_str, row_ind)
             for row_str, row_ind
             in zip("ABCDEFGH", range(0, 7))])
        self.artifact_id = artifact_id

    def get_key(self):
        return "{}:{}".format(self.row, self.col)

    def __repr__(self):
        return "{}:{}".format(self.row, self.col)

    def __str__(self):
        return "{} name={}, id={}".format(self.get_key().ljust(5, ' '), self.artifact_name,
                                          self.artifact_id)

    def get_coordinates(self):
        # Zero based
        return self.row_index_dict[self.row], int(self.col) - 1


# TODO: Use PlatePosition as plate key to handle different representations
from collections import namedtuple
class PlatePosition(namedtuple("PlatePosition", ["row", "col"])):
    pass

class Plate:
    """Encapsulates a Plate"""

    DOWN_FIRST = 1
    RIGHT_FIRST = 2

    def __init__(self, mapping=None):
        """
        :param mapping: A dictionary-like object containing mapping from well
        position to content. It can be non-complete.
        :return:
        """
        self.wells = {}
        for row, col in self._traverse():
            key = "{}:{}".format(row, col)
            content = mapping[key] if mapping and key in mapping else None
            self.wells[(row, col)] = Well(row, col, content)

    def _traverse(self, order=DOWN_FIRST):
        """Traverses the well in a certain order, yielding keys as (row,col) tuples"""

        # TODO: Provide support for other formats
        # TODO: Make use of functional prog. - and remove dup.
        # TODO: NOTE! RIGHT_FIRST/DOWN_FIRST where switched. Fix all scripts before checking in.
        if order == self.RIGHT_FIRST:
            for row in "ABCDEFGH":
                for col in range(1, 13):
                    yield (row, col)
        else:
            for col in range(1, 13):
                for row in "ABCDEFGH":
                    yield (row, col)

    # Lists the wells in a certain order:
    def enumerate_wells(self, order=DOWN_FIRST):
        for key in self._traverse(order):
            yield self.wells[key]

    def list_wells(self, order=DOWN_FIRST):
        return list(self.enumerate_wells(order))

    def set_well(self, well_id, artifact_name, artifact_id=None):
        """
        well_id should be a string in the format 'B:1'
        """
        if type(well_id) is str:
            split = well_id.split(":")
            well_id = split[0], int(split[1])

        if well_id not in self.wells:
            raise KeyError("Well id {} is not available in this plate".format(well_id))

        # TODO: Change the parameter to accepting a Well class instead
        self.wells[well_id].artifact_name = artifact_name
        self.wells[well_id].artifact_id = artifact_id

    def well_key_to_tuple(self, key):
        return key.split(":")

class ValidationType:
    ERROR = 1
    WARNING = 2


class ValidationException:
    def __init__(self, msg, validation_type=ValidationType.ERROR):
        self.msg = msg
        self.type = validation_type

    def _repr_type(self):
        if self.type == ValidationType.ERROR:
            return "Error"
        elif self.type == ValidationType.WARNING:
            return "Warning"

    def __repr__(self):
        return "{}: {}".format(self._repr_type(), self.msg)
