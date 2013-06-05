"""
"""
import itertools
from operator import attrgetter
from grendel.gmath.vector import Vector
from grendel.symmetry import GroupTheoryError
from conjugacy_class import ConjugacyClass
from grendel.symmetry.inversion import Inversion
from identity_operation import IdentityOperation
from improper_rotation import ImproperRotation
from reflection import Reflection
from rotation import Rotation
from grendel.util.decorators import CachedProperty
from symmetry_operation import SymmetryOperation
from grendel.util.units import *

__all__ = [
    'PointGroup',
]

class PointGroup(object):
    """ Encapsulates a point group.
    """

    ####################
    # Class Attributes #
    ####################

    symmetry_tolerance = 1e-4
    ring_angle_tolerance = 2 * Degrees.to(Radians)


    ##############
    # Attributes #
    ##############

    # TODO make some (all?) of these readonly properties
    operations = []
    molecule = None
    classes = []
    name = None


    ######################
    # Private Attributes #
    ######################

    _generate_elements = False


    ##################
    # Initialization #
    ##################

    def __init__(self, molecule, ops):
        """ Create a point group generated by the operators `generators`

        Parameters
        ----------
        generators : iterable of SymmetryOperation
            A (not necessarily minimal) set of operations that generate the group.

        """
        if any(not isinstance(obj, SymmetryOperation) for obj in ops):
            raise TypeError
        self.molecule = molecule
        self.classes = []
        self.operations = []
        self.name = None
        self.operations = list(ops)
        for op in self:
            op.point_group = self
        self._check_closure()
        self._compute_classes()
        self._name_operations()
        self._get_name()


    ##############
    # Properties #
    ##############

    @CachedProperty
    def identity_element(self):
        for op in self:
            if isinstance(op, IdentityOperation):
                return op
        raise GroupTheoryError("Group missing identity element!")

    @CachedProperty
    def rotations(self):
        ret_val = []
        for op in self:
            if isinstance(op, Rotation):
                ret_val.append(op)
        return ret_val

    @CachedProperty
    def improper_rotations(self):
        ret_val = []
        for op in self:
            if isinstance(op, ImproperRotation):
                ret_val.append(op)
        return ret_val

    @CachedProperty
    def reflections(self):
        ret_val = []
        for op in self:
            if isinstance(op, Reflection):
                ret_val.append(op)
        return ret_val

    @CachedProperty
    def inversion(self):
        ret_val = []
        for op in self:
            if isinstance(op, Inversion):
                return op
        return None


    ###################
    # Special Methods #
    ###################

    def __str__(self):
        return self.name

    def __repr__(self):
        return '<PointGroup named \'' + self.name + '\'>'

    def __iter__(self):
        return itertools.chain(self.operations)

    def __len__(self):
        return len(self.operations)

    ###########
    # Methods #
    ###########

    def element_for(self, op):
        """ Returns the element that is the same as `op` in the group `self`.
        This allows us to avoid duplication.  When self._generate_elements is True,
        this adds `op` to self.operations if no operation is found that is the same as `op` (this should pretty
        much only be used by the internal PointGroup._close_group() private method.  If you come up with
        another use for it, use it with care!)  Otherwise, if an equivalent of `op` is not found,
        a `GroupTheoryError` is raised.
        """
        if op in self.operations:
            return self.operations[self.operations.index(op)]
        elif self._generate_elements:
            self.operations.append(op)
            return op
        else:
            raise GroupTheoryError("Operation " + str(op) + " not found in group.")

    def element_with_matrix(self, mat):
        """ Returns the element that has the matrix `mat` in the group `self`.
        Raises a `GroupTheoryError` indicating the group is not closed if no such element is found.
        """
        for op in self:
            if SymmetryOperation.is_same_matrix(op.matrix, mat):
                return op
        mat_list = [str(op.matrix) for op in sorted(self, key=lambda o: (o.matrix-mat).norm())]
        raise GroupTheoryError("Group not closed:  In group with elements: \n[" + ", ".join(str(el) for el in self)
                               + "],\n Could not find element with the following matrix:\n"
                               + str(mat) + " in list (" + str(len(mat_list))
                               + " operations total):\n" + ",\n".join(mat_list))


    def num_C_n_axes(self, n):
        """ Returns the number of (unique) axes of order `n` in the point group
        """
        return len([rot for rot in self.rotations if rot.n == n and rot.exponent == 1])


    ####################
    # Private Methods #
    ####################

    def _check_closure(self):
        """ Checks that the group is closed under multiplication and finds the inverse of each element.
        """
        for iop in self:
            for jop in self:
                if iop * jop == self.identity_element:
                    if (not iop.inverse is None and not iop.inverse == jop) \
                        or (not jop.inverse is None and not jop.inverse == iop):
                        raise GroupTheoryError("Inverse of group element " + repr(iop) + " is not unique.")
                    iop.inverse = jop
                    jop.inverse = iop

    def _compute_classes(self):
        """ Computes the conjugacy classes of self.
        """
        for op in self:
            op_classes = list([cl for cl in self.classes if op in cl])
            if len(op_classes) == 0:
                op_class = ConjugacyClass(op)
                self.classes.append(op_class)
            elif len(op_classes) == 1:
                op_class = op_classes[0]
            else: # pragma: no cover
                raise GroupTheoryError("Conjugacy classes not disjoint.")
            for g in self:
                if g is op: continue
                op_class.add_element(g * op * g.inverse)

    def _name_operations(self):
        """ Determines the most-likely-to-be human-readable names for the operations.
        """

        # Figure out the principal reflections (sigma_h's)
        principal_rotations = []
        for k, g in itertools.groupby(sorted(self.rotations), attrgetter('n', 'exponent')):
            principal_rotations = list(g)
            break
        if len(principal_rotations) > 0:
            if principal_rotations[0].n > 2:
                # Mark them all as sigma_h's
                for rot in principal_rotations:
                    for op in self.reflections:
                        if SymmetryOperation.is_same_axis(op.axis, rot.axis):
                            op.principal_reflection = True
            else:
                # Otherwise, just choose the Z axis
                for op in self.reflections:
                    if SymmetryOperation.is_same_axis(op.axis, principal_rotations[0].axis):
                        op.principal_reflection = True
                        break
        self.operations.sort()
        self._rotations = None
        self._improper_rotations = None
        self._reflections = None
        self.identity_element.name = "E"
        if not self.inversion is None:
            self.inversion.name = 'i'
        for key, rotiter in itertools.groupby(self.rotations, attrgetter('n')):
            rotgrp = list(rotiter)
            prime_count = 0
            labels = []
            order = rotgrp[0].n
            if len(rotgrp) == rotgrp[0].n - 1:
                # only one axis, label it simply
                rotgrp[0].name = "C_" + str(order)
                for i in xrange(1, len(rotgrp)):
                    rotgrp[i].name = "C_" + str(order) + "^" + str(rotgrp[i].exponent)
            else:
                naxes = len([x for x in rotgrp if x.exponent == 1])
                has_paren_label = False
                for i, rot in enumerate(rotgrp):
                    if i < naxes:
                        if SymmetryOperation.is_same_axis(rot.axis, Vector(0,0,1)):
                            labels.append("(z)")
                            has_paren_label = True
                            rot.name = "C_" + str(order) + "(z)"
                        elif SymmetryOperation.is_same_axis(rot.axis, Vector(0,1,1)):
                            labels.append("(y)")
                            has_paren_label = True
                            rot.name = "C_" + str(order) + "(y)"
                        elif SymmetryOperation.is_same_axis(rot.axis, Vector(1,0,0)):
                            labels.append("(x)")
                            has_paren_label = True
                            rot.name = "C_" + str(order) + "(x)"
                        else:
                            label = "'" * (prime_count + (1 if has_paren_label else 0))
                            labels.append(label)
                            prime_count += 1
                            rot.name = "C_" + str(order) + label
                    else:
                        rot.name = "C_" + str(order) + labels[i % naxes] + "^" + str(rot.exponent)
        for key, rotiter in itertools.groupby(self.improper_rotations, attrgetter('n')):
            rotgrp = list(rotiter)
            prime_count = 0
            labels = []
            order = rotgrp[0].n
            if len(rotgrp) == rotgrp[0].n - 1:
                # only one axis, label it simply
                rotgrp[0].name = "S_" + str(order)
                for i in xrange(1, len(rotgrp)):
                    rotgrp[i].name = "S_" + str(order) + "^" + str(rotgrp[i].exponent)
            else:
                has_paren_label = False
                naxes = len([x for x in rotgrp if x.exponent == 1])
                for i, rot in enumerate(rotgrp):
                    if i < naxes:
                        if SymmetryOperation.is_same_axis(rot.axis, Vector(0,0,1)):
                            labels.append("(z)")
                            has_paren_label = True
                            rot.name = "S_" + str(order) + "(z)"
                        elif SymmetryOperation.is_same_axis(rot.axis, Vector(0,1,0)):
                            labels.append("(y)")
                            has_paren_label = True
                            rot.name = "S_" + str(order) + "(y)"
                        elif SymmetryOperation.is_same_axis(rot.axis, Vector(1,0,0)):
                            labels.append("(x)")
                            has_paren_label = True
                            rot.name = "S_" + str(order) + "(x)"
                        else:
                            label = "'" * (prime_count + (1 if has_paren_label else 0))
                            labels.append(label)
                            prime_count += 1
                            rot.name = "S_" + str(order) + label
                    else:
                        rot.name = "S_" + str(order) + labels[i % naxes] + "^" + str(rot.exponent)
        prime_count = {'v':0, 'd':0,'h':0}
        has_paren_label = False
        for ref in self.reflections:
            subscript = ''
            if ref.is_principal_reflection():
                subscript = 'h'
            elif ref.is_dihedral():
                subscript = 'd'
            else:
                subscript = 'v'
            if SymmetryOperation.is_same_axis(ref.axis, Vector(0,0,1)):
                ref.name = "sigma_"+ subscript + "(xy)"
                has_paren_label = True
            elif SymmetryOperation.is_same_axis(ref.axis, Vector(0,1,0)):
                ref.name = "sigma_" + subscript + "(xz)"
                has_paren_label = True
            elif SymmetryOperation.is_same_axis(ref.axis, Vector(1,0,0)):
                ref.name = "sigma_" + subscript + "(yz)"
                has_paren_label = True
            else:
                label = "'" * (prime_count[subscript] + (1 if has_paren_label else 0))
                prime_count[subscript] += 1
                ref.name = "sigma_" + subscript + label
        self.classes.sort(key=attrgetter('first_element'))



    def _get_name(self):
        """ Get the name of the point group
        """
        # Using a flow charts from http://www.mineralatlas.com/fga/image007.gif and
        # http://capsicum.me.utexas.edu/ChE386K/html/flowchart_point_groups.htm
        # If two or more C_n with n > 2...
        if len([rot for rot in self.rotations if rot.n > 2 and rot.exponent == 1 ]) >= 2:
            # 12 C5 axes?
            if self.num_C_n_axes(5) == 12:
                if self.inversion is None:
                    self.name = 'I'
                    return
                else:
                    self.name = 'I_h'
                    return
            # 6 C4s?
            elif self.num_C_n_axes(4) == 6:
                if self.inversion is None:
                    self.name = 'O'
                    return
                else:
                    self.name = 'O_h'
                    return
            # 4 C3s?
            elif self.num_C_n_axes(3) == 4:
                # 8 C3s?
                if self.inversion is None:
                    if len(self.reflections) == 6:
                        self.name = 'T_d'
                        return
                    else:
                        self.name = 'T'
                        return
                else:
                    self.name = 'T_h'
                    return
            else:
                raise GroupTheoryError("Don't know the name of group with classes: " + str(self.classes)
                                        + ".  (Perhaps adjust tolerances?)")
        elif len(self.rotations) > 0:
            highest_Cn = self.rotations[0]
            highest_n = highest_Cn.n
            highest_axis = highest_Cn.axis
            count = 0
            for rot in self.rotations:
                if rot.n == 2 and SymmetryOperation.is_perpendicular(highest_axis, rot.axis):
                    count += 1
            if count == highest_n:
                if any(ref.is_principal_reflection() for ref in self.reflections):
                    self.name = 'D_' + str(highest_n) + 'h'
                    return
                elif len(self.reflections) == highest_n:
                    self.name = 'D_' + str(highest_n) + 'd'
                    return
                elif len(self.reflections) == 0:
                    self.name = 'D_' + str(highest_n)
                else:
                    raise GroupTheoryError("Don't know the name of group with classes: " + str(self.classes)
                                            + ".  (Perhaps adjust tolerances?)")
            else:
                if any(ref.is_principal_reflection() for ref in self.reflections):
                    self.name = 'C_' + str(highest_n) + 'h'
                    return
                elif len(self.reflections) == highest_n:
                    self.name = 'C_' + str(highest_n) + 'v'
                    return
                elif any(irot.n == 2*highest_n for irot in self.improper_rotations):
                    self.name = 'S_' + str(2*highest_n)
                    return
                else:
                    self.name = 'C_' + str(highest_n)
                    return
        else:
            if len(self.reflections) == 1:
                self.name = 'C_s'
                return
            elif not self.inversion is None:
                self.name = 'C_i'
                return
            elif len(self) == 1:
                self.name = 'C_1'
            else:
                raise GroupTheoryError("Don't know the name of group with classes: " + str(self.classes)
                                        + ".  (Perhaps adjust tolerances?)")








