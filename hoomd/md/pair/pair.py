# Copyright (c) 2009-2021 The Regents of the University of Michigan
# This file is part of the HOOMD-blue project, released under the BSD 3-Clause License.

import hoomd
from hoomd import _hoomd
from hoomd.md import _md
from hoomd.md import force
from hoomd.md import nlist as nl
from hoomd.md.nlist import NList
from hoomd.data.parameterdicts import ParameterDict, TypeParameterDict
from hoomd.data.typeparam import TypeParameter
from hoomd.data.typeconverter import (
    OnlyFrom, OnlyType, positive_real, nonnegative_real)

import math


validate_nlist = OnlyType(NList)


class Pair(force.Force):
    """Common pair potential documentation.

    Users should not invoke `Pair` directly. It is a base command
    that provides common features to all standard pair forces. Common
    documentation for all pair potentials is documented here.

    All pair force commands specify that a given potential energy and force be
    computed on all non-excluded particle pairs in the system within a short
    range cutoff distance :math:`r_{\\mathrm{cut}}`.

    The force :math:`\\vec{F}` applied between each pair of particles is:

    .. math::
        :nowrap:

        \\begin{eqnarray*}
        \\vec{F}  = & -\\nabla V(r) & r < r_{\\mathrm{cut}} \\\\
                  = & 0           & r \\ge r_{\\mathrm{cut}} \\\\
        \\end{eqnarray*}

    where :math:`\\vec{r}` is the vector pointing from one particle to the other
    in the pair, and :math:`V(r)` is chosen by a mode switch:

    .. math::
        :nowrap:

        \\begin{eqnarray*}
        V(r)  = & V_{\\mathrm{pair}}(r) & \\mathrm{mode\\ is\\ no\\_shift} \\\\
              = & V_{\\mathrm{pair}}(r) - V_{\\mathrm{pair}}(r_{\\mathrm{cut}})
              & \\mathrm{mode\\ is\\ shift} \\\\
              = & S(r) \\cdot V_{\\mathrm{pair}}(r) & \\mathrm{mode\\ is\\
              xplor\\ and\\ } r_{\\mathrm{on}} < r_{\\mathrm{cut}} \\\\
              = & V_{\\mathrm{pair}}(r) - V_{\\mathrm{pair}}(r_{\\mathrm{cut}})
              & \\mathrm{mode\\ is\\ xplor\\ and\\ } r_{\\mathrm{on}} \\ge
              r_{\\mathrm{cut}}
        \\end{eqnarray*}

    :math:`S(r)` is the XPLOR smoothing function:

    .. math::
        :nowrap:

        \\begin{eqnarray*}
        S(r) = & 1 & r < r_{\\mathrm{on}} \\\\
             = & \\frac{(r_{\\mathrm{cut}}^2 - r^2)^2 \\cdot
             (r_{\\mathrm{cut}}^2 + 2r^2 -
             3r_{\\mathrm{on}}^2)}{(r_{\\mathrm{cut}}^2 -
             r_{\\mathrm{on}}^2)^3}
               & r_{\\mathrm{on}} \\le r \\le r_{\\mathrm{cut}} \\\\
             = & 0 & r > r_{\\mathrm{cut}} \\\\
         \\end{eqnarray*}

    and :math:`V_{\\mathrm{pair}}(r)` is the specific pair potential chosen by
    the respective command.

    Enabling the XPLOR smoothing function :math:`S(r)` results in both the
    potential energy and the force going smoothly to 0 at :math:`r =
    r_{\\mathrm{cut}}`, reducing the rate of energy drift in long simulations.
    :math:`r_{\\mathrm{on}}` controls the point at which the smoothing starts,
    so it can be set to only slightly modify the tail of the potential. It is
    suggested that you plot your potentials with various values of
    :math:`r_{\\mathrm{on}}` in order to find a good balance between a smooth
    potential function and minimal modification of the original
    :math:`V_{\\mathrm{pair}}(r)`. A good value for the LJ potential is
    :math:`r_{\\mathrm{on}} = 2 \\cdot \\sigma`.

    The split smoothing / shifting of the potential when the mode is ``xplor``
    is designed for use in mixed WCA / LJ systems. The WCA potential and it's
    first derivative already go smoothly to 0 at the cutoff, so there is no need
    to apply the smoothing function. In such mixed systems, set
    :math:`r_{\\mathrm{on}}` to a value greater than :math:`r_{\\mathrm{cut}}`
    for those pairs that interact via WCA in order to enable shifting of the WCA
    potential to 0 at the cutoff.

    The following coefficients must be set per unique pair of particle types.
    See `hoomd.md.pair` for information on how to set coefficients.

    Attributes:
        r_cut (`TypeParameter` [\
          `tuple` [``particle_type``, ``particle_type``],\
          `float`]): *r_cut* (in distance units), *optional*: defaults to the
          value ``r_cut`` specificied on construction

        r_on (`TypeParameter` [\
          `tuple` [``particle_type``, ``particle_type``],\
          `float`]): *r_on* (in distance units),  *optional*: defaults to the
          value ``r_on`` specified on construction
    """

    def __init__(self, nlist, r_cut=None, r_on=0., mode='none'):
        self._nlist = validate_nlist(nlist)
        tp_r_cut = TypeParameter('r_cut', 'particle_types',
                                 TypeParameterDict(positive_real, len_keys=2)
                                 )
        if r_cut is not None:
            tp_r_cut.default = r_cut
        tp_r_on = TypeParameter('r_on', 'particle_types',
                                TypeParameterDict(nonnegative_real, len_keys=2)
                                )
        if r_on is not None:
            tp_r_on.default = r_on
        self._extend_typeparam([tp_r_cut, tp_r_on])
        self._param_dict.update(
            ParameterDict(mode=OnlyFrom(['none', 'shift', 'xplor'])))
        self.mode = mode

    def compute_energy(self, tags1, tags2):
        R""" Compute the energy between two sets of particles.

        Args:
            tags1 (``ndarray<int32>``): a numpy array of particle tags in the
                first group
            tags2 (``ndarray<int32>``): a numpy array of particle tags in the
                second group

        .. math::

            U = \sum_{i \in \mathrm{tags1}, j \in \mathrm{tags2}} V_{ij}(r)

        where :math:`V_{ij}(r)` is the pairwise energy between two particles
        :math:`i` and :math:`j`.

        Assumed properties of the sets *tags1* and *tags2* are:

        - *tags1* and *tags2* are disjoint
        - all elements in *tags1* and *tags2* are unique
        - *tags1* and *tags2* are contiguous numpy arrays of dtype int32

        None of these properties are validated.

        Examples::

            tags=numpy.linspace(0,N-1,1, dtype=numpy.int32)
            # computes the energy between even and odd particles
            U = mypair.compute_energy(tags1=numpy.array(tags[0:N:2]),
                                      tags2=numpy.array(tags[1:N:2]))

        """
        # TODO future versions could use np functions to test the assumptions
        # above and raise an error if they occur.
        return self._cpp_obj.computeEnergyBetweenSets(tags1, tags2)

    def _attach(self):
        # create the c++ mirror class
        if not self._nlist._added:
            self._nlist._add(self._simulation)
        else:
            if self._simulation != self._nlist._simulation:
                raise RuntimeError("{} object's neighbor list is used in a "
                                   "different simulation.".format(type(self)))
        if not self.nlist._attached:
            self.nlist._attach()
        if isinstance(self._simulation.device, hoomd.device.CPU):
            cls = getattr(_md, self._cpp_class_name)
            self.nlist._cpp_obj.setStorageMode(
                _md.NeighborList.storageMode.half)
        else:
            cls = getattr(_md, self._cpp_class_name + "GPU")
            self.nlist._cpp_obj.setStorageMode(
                _md.NeighborList.storageMode.full)
        self._cpp_obj = cls(
            self._simulation.state._cpp_sys_def, self.nlist._cpp_obj,
            '')  # TODO remove name string arg

        super()._attach()

    @property
    def nlist(self):
        return self._nlist

    @nlist.setter
    def nlist(self, value):
        if self._attached:
            raise RuntimeError("nlist cannot be set after scheduling.")
        else:
            self._nlist = validate_nlist(value)

    @property
    def _children(self):
        return [self.nlist]


class LJ(Pair):
    """ Lennard-Jones pair potential.

    Args:
        nlist (`hoomd.md.nlist.NList`): Neighbor list
        r_cut (float): Default cutoff radius (in distance units).
        r_on (float): Default turn-on radius (in distance units).
        mode (str): energy shifting/smoothing mode

    `LJ` specifies that a Lennard-Jones pair potential should be
    applied between every non-excluded particle pair in the simulation.

    .. math::
        :nowrap:

        \\begin{eqnarray*}
        V_{\\mathrm{LJ}}(r)  = & 4 \\varepsilon \\left[ \\left(
        \\frac{\\sigma}{r} \\right)^{12} - \\left( \\frac{\\sigma}{r}
        \\right)^{6} \\right] & r < r_{\\mathrm{cut}} \\\\
        = & 0 & r \\ge r_{\\mathrm{cut}} \\\\
        \\end{eqnarray*}

    See `Pair` for details on how forces are calculated and the
    available energy shifting and smoothing modes.  Use `params` dictionary
    to set potential coefficients. The coefficients must be set per
    unique pair of particle types.

    Attributes:
        params (`TypeParameter` [\
            `tuple` [``particle_type``, ``particle_type``],\
            `dict`]):
            The LJ potential parameters. The dictionary has the following keys:

            * ``epsilon`` (`float`, **required**) -
              energy parameter :math:`\\varepsilon` (in energy units)

            * ``sigma`` (`float`, **required**) -
              particle size :math:`\\sigma` (in distance units)

    Example::

        nl = nlist.Cell()
        lj = pair.LJ(nl, r_cut=3.0)
        lj.params[('A', 'A')] = {'sigma': 1.0, 'epsilon': 1.0}
        lj.r_cut[('A', 'B')] = 3.0
    """
    _cpp_class_name = "PotentialPairLJ"

    def __init__(self, nlist, r_cut=None, r_on=0., mode='none'):
        super().__init__(nlist, r_cut, r_on, mode)
        params = TypeParameter('params', 'particle_types',
                               TypeParameterDict(epsilon=float, sigma=float,
                                                 len_keys=2)
                               )
        self._add_typeparam(params)


class Gauss(Pair):
    """ Gaussian pair potential.

    Args:
        nlist (`hoomd.md.nlist.NList`): Neighbor list
        r_cut (float): Default cutoff radius (in distance units).
        r_on (float): Default turn-on radius (in distance units).
        mode (str): energy shifting/smoothing mode.

    `Gauss` specifies that a Gaussian pair potential should be applied
    between every non-excluded particle pair in the simulation.

    .. math::
        :nowrap:

        \\begin{eqnarray*}
        V_{\\mathrm{gauss}}(r)  = & \\varepsilon \\exp \\left[ -\\frac{1}{2}
                                  \\left( \\frac{r}{\\sigma} \\right)^2 \\right]
                                  & r < r_{\\mathrm{cut}} \\\\
                                 = & 0 & r \\ge r_{\\mathrm{cut}} \\\\
        \\end{eqnarray*}

    See `Pair` for details on how forces are calculated and the
    available energy shifting and smoothing modes. Use `params` dictionary to
    set potential coefficients. The coefficients must be set per unique pair of
    particle types.

    Attributes:
        params (`TypeParameter` [\
          `tuple` [``particle_type``, ``particle_type``],\
          `dict`]):
          The Gauss potential parameters. The dictionary has the following
          keys:

          * ``epsilon`` (`float`, **required**) - energy parameter
            :math:`\\varepsilon` (in energy units)

          * ``sigma`` (`float`, **required**) - particle size :math:`\\sigma`
            (in distance units)

    Example::

        nl = nlist.Cell()
        gauss = pair.Gauss(r_cut=3.0, nlist=nl)
        gauss.params[('A', 'A')] = dict(epsilon=1.0, sigma=1.0)
        gauss.r_cut[('A', 'B')] = 3.0
    """
    _cpp_class_name = "PotentialPairGauss"
    def __init__(self, nlist, r_cut=None, r_on=0., mode='none'):
        super().__init__(nlist, r_cut, r_on, mode)
        params = TypeParameter('params', 'particle_types',
                               TypeParameterDict(epsilon=float, sigma=float,
                                                 len_keys=2))
        self._add_typeparam(params)


class SLJ(Pair):
    """Shifted Lennard-Jones pair potential.

    Args:
        nlist (`hoomd.md.nlist.NList`): Neighbor list
        r_cut (float): Default cutoff radius (in distance units).
        r_on (float): Default turn-on radius (in distance units).
        mode (str): Energy shifting/smoothing mode

    `SLJ` specifies that a shifted Lennard-Jones type pair potential
    should be applied between every non-excluded particle pair in the
    simulation.

    .. math::
        :nowrap:

        \\begin{eqnarray*}
        V_{\\mathrm{SLJ}}(r)  = & 4 \\varepsilon \\left[ \\left(
                                \\frac{\\sigma}{r - \\Delta} \\right)^{12} -
                                \\left( \\frac{\\sigma}{r - \\Delta}
                                \\right)^{6} \\right] & r < (r_{\\mathrm{cut}}
                                + \\Delta) \\\\
                             = & 0 & r \\ge (r_{\\mathrm{cut}} + \\Delta) \\\\
        \\end{eqnarray*}

    where :math:`\\Delta = (d_i + d_j)/2 - 1` and :math:`d_i` is the diameter of
    particle :math:`i`.

    See `Pair` for details on how forces are calculated and the
    available energy shifting and smoothing modes. Use `params` dictionary to
    set potential coefficients. The coefficients must be set per unique pair of
    particle types.

    Attention:
        Due to the way that `SLJ` modifies the cutoff criteria, a shift_mode
        of *xplor* is not supported.

    Set the ``max_diameter`` property of the neighbor list object to the largest
    particle diameter in the system (where **diameter** is a per-particle
    property of the same name in `hoomd.State`).

    Warning:
        Failure to set ``max_diameter`` will result in missing pair
        interactions.

    Attributes:
        params (`TypeParameter` [\
            `tuple` [``particle_type``, ``particle_type``],\
            `dict`]):
            The potential parameters. The dictionary has the following keys:

            * ``epsilon`` (`float`, **required**) - energy parameter
              :math:`\\varepsilon` (in energy units)

            * ``sigma`` (`float`, **required**) - particle size :math:`\\sigma`
              (in distance units)

    Example::

        nl = nlist.Cell()
        nl.max_diameter = 2.0
        slj = pair.SLJ(r_cut=3.0, nlist=nl)
        slj.params[('A', 'B')] = dict(epsilon=2.0, r_cut=3.0)
        slj.r_cut[('B', 'B')] = 2**(1.0/6.0)
    """
    _cpp_class_name = 'PotentialPairSLJ'
    def __init__(self, nlist, r_cut=None, r_on=0., mode='none'):
        if mode == 'xplor':
            raise ValueError("xplor is not a valid mode for SLJ potential")

        super().__init__(nlist, r_cut, r_on, mode)
        params = TypeParameter('params', 'particle_types',
                               TypeParameterDict(epsilon=float, sigma=float,
                                                 alpha=1.0, len_keys=2)
                               )
        self._add_typeparam(params)

        # mode not allowed to be xplor, so re-do param dict entry without that option
        param_dict = ParameterDict(mode=OnlyFrom(['none', 'shift']))
        self._param_dict.update(param_dict)
        self.mode = mode

        # this potential needs diameter shifting on
        self._nlist.diameter_shift = True

        # NOTE do we need something to automatically set the max_diameter correctly?


class Yukawa(Pair):
    """Yukawa pair potential.

    Args:
        nlist (`hoomd.md.nlist.NList`): Neighbor list
        r_cut (float): Default cutoff radius (in distance units).
        r_on (float): Default turn-on radius (in distance units).
        mode (str): Energy shifting mode.

    `Yukawa` specifies that a Yukawa pair potential should be applied between
    every non-excluded particle pair in the simulation.

    .. math::
        :nowrap:

        \\begin{eqnarray*}
          V_{\\mathrm{yukawa}}(r) = & \\varepsilon \\frac{ \\exp \\left(
          -\\kappa r \\right) }{r} & r < r_{\\mathrm{cut}} \\\\
                                  = & 0 & r \\ge r_{\\mathrm{cut}} \\\\
        \\end{eqnarray*}

    See `Pair` for details on how forces are calculated and the available
    energy shifting and smoothing modes. Use `params` dictionary to set
    potential coefficients. The coefficients must be set per unique pair of
    particle types.

    Attributes:
        params (`TypeParameter` [\
          `tuple` [``particle_type``, ``particle_type``],\
          `dict`]):
          The Yukawa potential parameters. The dictionary has the following
          keys:

          * ``epsilon`` (`float`, **required**) - energy parameter
            :math:`\\varepsilon` (in energy units)

          * ``kappa`` (`float`, **required**) - scaling parameter
            :math:`\\kappa` (in units of 1/distance)

    Example::

        nl = nlist.Cell()
        yukawa = pair.Yukawa(r_cut=3.0, nlist=nl)
        yukawa.params[('A', 'A')] = dict(epsilon=1.0, kappa=1.0)
        yukawa.r_cut[('A', 'B')] = 3.0
    """
    _cpp_class_name = "PotentialPairYukawa"
    def __init__(self, nlist, r_cut=None, r_on=0., mode='none'):
        super().__init__(nlist, r_cut, r_on, mode)
        params = TypeParameter('params', 'particle_types',
                               TypeParameterDict(kappa=float, epsilon=float,
                                                 len_keys=2))
        self._add_typeparam(params)


class Ewald(Pair):
    """Ewald pair potential.

    Args:
        nlist (`hoomd.md.nlist.NList`): Neighbor list
        r_cut (float): Default cutoff radius (in distance units).
        r_on (float): Default turn-on radius (in distance units).
        mode (str): Energy shifting mode.

    `Ewald` specifies that a Ewald pair potential should be applied between
    every non-excluded particle pair in the simulation.

    .. math::
        :nowrap:

        \\begin{eqnarray*}
         V_{\\mathrm{ewald}}(r)  = & q_i q_j \\left[\\mathrm{erfc}\\left(\\kappa
                                    r + \\frac{\\alpha}{2\\kappa}\\right)
                                    \\exp(\\alpha r) \\\\
                                    + \\mathrm{erfc}\\left(\\kappa r -
                                    \\frac{\\alpha}{2 \\kappa}\\right)
                                    \\exp(-\\alpha r)\\right]
                                    & r < r_{\\mathrm{cut}} \\\\
                            = & 0 & r \\ge r_{\\mathrm{cut}} \\\\
        \\end{eqnarray*}

    The Ewald potential is designed to be used in conjunction with PPPM.

    See `Pair` for details on how forces are calculated and the available
    energy shifting and smoothing modes. Use the `params` dictionary to set
    potential coefficients. The coefficients must be set per unique pair of
    particle types.

    Attributes:
        params (`TypeParameter` [\
          `tuple` [``particle_type``, ``particle_type``],\
          `dict`]):
          The Ewald potential parameters. The dictionary has the following keys:

          * ``kappa`` (`float`, **required**) - Splitting parameter
            :math:`\\kappa` (in units of 1/distance)

          * ``alpha`` (`float`, **required**) - Debye screening length
            :math:`\\alpha` (in units of 1/distance)

    Example::

        nl = nlist.Cell()
        ewald = pair.Ewald(r_cut=3.0, nlist=nl)
        ewald.params[('A', 'A')] = dict(kappa=1.0, alpha=1.5)
        ewald.r_cut[('A', 'B')] = 3.0
    """
    _cpp_class_name = "PotentialPairEwald"
    def __init__(self, nlist, r_cut=None, r_on=0., mode='none'):
        super().__init__(nlist, r_cut, r_on, mode)
        params = TypeParameter('params', 'particle_types',
                               TypeParameterDict(kappa=float, alpha=0.0,
                                             len_keys=2))
        self._add_typeparam(params)


def _table_eval(r, rmin, rmax, V, F, width):
    dr = (rmax - rmin) / float(width-1);
    i = int(round((r - rmin)/dr))
    return (V[i], F[i])


class table(force._force):
    R""" Tabulated pair potential.

    Args:
        width (int): Number of points to use to interpolate V and F.
        nlist (`hoomd.md.nlist.NList`): Neighbor list (default of None automatically creates a global cell-list based neighbor list)
        name (str): Name of the force instance

    :py:class:`table` specifies that a tabulated pair potential should be applied between every
    non-excluded particle pair in the simulation.

    The force :math:`\vec{F}` is (in force units):

    .. math::
        :nowrap:

        \begin{eqnarray*}
        \vec{F}(\vec{r})     = & 0                           & r < r_{\mathrm{min}} \\
                             = & F_{\mathrm{user}}(r)\hat{r} & r_{\mathrm{min}} \le r < r_{\mathrm{max}} \\
                             = & 0                           & r \ge r_{\mathrm{max}} \\
        \end{eqnarray*}

    and the potential :math:`V(r)` is (in energy units)

    .. math::
        :nowrap:

        \begin{eqnarray*}
        V(r)       = & 0                    & r < r_{\mathrm{min}} \\
                   = & V_{\mathrm{user}}(r) & r_{\mathrm{min}} \le r < r_{\mathrm{max}} \\
                   = & 0                    & r \ge r_{\mathrm{max}} \\
        \end{eqnarray*}

    where :math:`\vec{r}` is the vector pointing from one particle to the other in the pair.

    :math:`F_{\mathrm{user}}(r)` and :math:`V_{\mathrm{user}}(r)` are evaluated on *width* grid points between
    :math:`r_{\mathrm{min}}` and :math:`r_{\mathrm{max}}`. Values are interpolated linearly between grid points.
    For correctness, you must specify the force defined by: :math:`F = -\frac{\partial V}{\partial r}`.

    The following coefficients must be set per unique pair of particle types:

    - :math:`V_{\mathrm{user}}(r)` and :math:`F_{\mathrm{user}}(r)` - evaluated by ``func`` (see example)
    - coefficients passed to ``func`` - *coeff* (see example)
    - :math:`_{\mathrm{min}}` - *rmin* (in distance units)
    - :math:`_{\mathrm{max}}` - *rmax* (in distance units)

    .. rubric:: Set table from a given function

    When you have a functional form for V and F, you can enter that
    directly into python. :py:class:`table` will evaluate the given function over *width* points between
    *rmin* and *rmax* and use the resulting values in the table::

        def lj(r, rmin, rmax, epsilon, sigma):
            V = 4 * epsilon * ( (sigma / r)**12 - (sigma / r)**6);
            F = 4 * epsilon / r * ( 12 * (sigma / r)**12 - 6 * (sigma / r)**6);
            return (V, F)

        nl = nlist.cell()
        table = pair.table(width=1000, nlist=nl)
        table.pair_coeff.set('A', 'A', func=lj, rmin=0.8, rmax=3.0, coeff=dict(epsilon=1.5, sigma=1.0))
        table.pair_coeff.set('A', 'B', func=lj, rmin=0.8, rmax=3.0, coeff=dict(epsilon=2.0, sigma=1.2))
        table.pair_coeff.set('B', 'B', func=lj, rmin=0.8, rmax=3.0, coeff=dict(epsilon=0.5, sigma=1.0))

    .. rubric:: Set a table from a file

    When you have no function for for *V* or *F*, or you otherwise have the data listed in a file,
    :py:class:`table` can use the given values directly. You must first specify the number of rows
    in your tables when initializing pair.table. Then use :py:meth:`set_from_file()` to read the file::

        nl = nlist.cell()
        table = pair.table(width=1000, nlist=nl)
        table.set_from_file('A', 'A', filename='table_AA.dat')
        table.set_from_file('A', 'B', filename='table_AB.dat')
        table.set_from_file('B', 'B', filename='table_BB.dat')

    Note:
        For potentials that diverge near r=0, make sure to set *rmin* to a reasonable value. If a potential does
        not diverge near r=0, then a setting of *rmin=0* is valid.

    """
    def __init__(self, width, nlist, name=None):

        # initialize the base class
        force._force.__init__(self, name);

        # setup the coefficient matrix
        self.pair_coeff = coeff();

        self.nlist = nlist
        self.nlist.subscribe(lambda:self.get_rcut())
        self.nlist.update_rcut()

        # create the c++ mirror class
        if not hoomd.context.current.device.cpp_exec_conf.isCUDAEnabled():
            self.cpp_force = _md.TablePotential(hoomd.context.current.system_definition, self.nlist.cpp_nlist, int(width), self.name);
        else:
            self.nlist.cpp_nlist.setStorageMode(_md.NeighborList.storageMode.full);
            self.cpp_force = _md.TablePotentialGPU(hoomd.context.current.system_definition, self.nlist.cpp_nlist, int(width), self.name);

        hoomd.context.current.system.addCompute(self.cpp_force, self.force_name);

        # stash the width for later use
        self.width = width;

    def update_pair_table(self, typei, typej, func, rmin, rmax, coeff):
        # allocate arrays to store V and F
        Vtable = _hoomd.std_vector_scalar();
        Ftable = _hoomd.std_vector_scalar();

        # calculate dr
        dr = (rmax - rmin) / float(self.width-1);

        # evaluate each point of the function
        for i in range(0, self.width):
            r = rmin + dr * i;
            (V,F) = func(r, rmin, rmax, **coeff);

            # fill out the tables
            Vtable.append(V);
            Ftable.append(F);

        # pass the tables on to the underlying cpp compute
        self.cpp_force.setTable(typei, typej, Vtable, Ftable, rmin, rmax);

    ## \internal
    # \brief Get the r_cut pair dictionary
    # \returns rcut(i,j) dict if logging is on, and None otherwise
    def get_rcut(self):
        if not self.log:
            return None

        # go through the list of only the active particle types in the sim
        ntypes = hoomd.context.current.system_definition.getParticleData().getNTypes();
        type_list = [];
        for i in range(0,ntypes):
            type_list.append(hoomd.context.current.system_definition.getParticleData().getNameByType(i));

        # update the rcut by pair type
        r_cut_dict = nl.rcut();
        for i in range(0,ntypes):
            for j in range(i,ntypes):
                # get the r_cut value
                rmax = self.pair_coeff.get(type_list[i], type_list[j], 'rmax');
                r_cut_dict.set_pair(type_list[i],type_list[j], rmax);

        return r_cut_dict;

    def get_max_rcut(self):
        # loop only over current particle types
        ntypes = hoomd.context.current.system_definition.getParticleData().getNTypes();
        type_list = [];
        for i in range(0,ntypes):
            type_list.append(hoomd.context.current.system_definition.getParticleData().getNameByType(i));

        # find the maximum rmax to update the neighbor list with
        maxrmax = 0.0;

        # loop through all of the unique type pairs and find the maximum rmax
        for i in range(0,ntypes):
            for j in range(i,ntypes):
                rmax = self.pair_coeff.get(type_list[i], type_list[j], "rmax");
                maxrmax = max(maxrmax, rmax);

        return maxrmax;

    def update_coeffs(self):
        # check that the pair coefficients are valid
        if not self.pair_coeff.verify(["func", "rmin", "rmax", "coeff"]):
            hoomd.context.current.device.cpp_msg.error("Not all pair coefficients are set for pair.table\n");
            raise RuntimeError("Error updating pair coefficients");

        # set all the params
        ntypes = hoomd.context.current.system_definition.getParticleData().getNTypes();
        type_list = [];
        for i in range(0,ntypes):
            type_list.append(hoomd.context.current.system_definition.getParticleData().getNameByType(i));

        # loop through all of the unique type pairs and evaluate the table
        for i in range(0,ntypes):
            for j in range(i,ntypes):
                func = self.pair_coeff.get(type_list[i], type_list[j], "func");
                rmin = self.pair_coeff.get(type_list[i], type_list[j], "rmin");
                rmax = self.pair_coeff.get(type_list[i], type_list[j], "rmax");
                coeff = self.pair_coeff.get(type_list[i], type_list[j], "coeff");

                self.update_pair_table(i, j, func, rmin, rmax, coeff);

    def set_from_file(self, a, b, filename):
        R""" Set a pair interaction from a file.

        Args:
            a (str): Name of type A in pair
            b (str): Name of type B in pair
            filename (str): Name of the file to read

        The provided file specifies V and F at equally spaced r values.

        Example::

            #r  V    F
            1.0 2.0 -3.0
            1.1 3.0 -4.0
            1.2 2.0 -3.0
            1.3 1.0 -2.0
            1.4 0.0 -1.0
            1.5 -1.0 0.0

        The first r value sets *rmin*, the last sets *rmax*. Any line with # as the first non-whitespace character is
        is treated as a comment. The *r* values must monotonically increase and be equally spaced. The table is read
        directly into the grid points used to evaluate :math:`F_{\mathrm{user}}(r)` and :math:`_{\mathrm{user}}(r)`.
        """

        # open the file
        f = open(filename);

        r_table = [];
        V_table = [];
        F_table = [];

        # read in lines from the file
        for line in f.readlines():
            line = line.strip();

            # skip comment lines
            if line[0] == '#':
                continue;

            # split out the columns
            cols = line.split();
            values = [float(f) for f in cols];

            # validate the input
            if len(values) != 3:
                hoomd.context.current.device.cpp_msg.error("pair.table: file must have exactly 3 columns\n");
                raise RuntimeError("Error reading table file");

            # append to the tables
            r_table.append(values[0]);
            V_table.append(values[1]);
            F_table.append(values[2]);

        # validate input
        if self.width != len(r_table):
            hoomd.context.current.device.cpp_msg.error("pair.table: file must have exactly " + str(self.width) + " rows\n");
            raise RuntimeError("Error reading table file");

        # extract rmin and rmax
        rmin_table = r_table[0];
        rmax_table = r_table[-1];

        # check for even spacing
        dr = (rmax_table - rmin_table) / float(self.width-1);
        for i in range(0,self.width):
            r = rmin_table + dr * i;
            if math.fabs(r - r_table[i]) > 1e-3:
                hoomd.context.current.device.cpp_msg.error("pair.table: r must be monotonically increasing and evenly spaced\n");
                raise RuntimeError("Error reading table file");

        self.pair_coeff.set(a, b, func=_table_eval, rmin=rmin_table, rmax=rmax_table, coeff=dict(V=V_table, F=F_table, width=self.width))


class Morse(Pair):
    """Morse pair potential.

    Args:
        nlist (`hoomd.md.nlist.NList`): Neighbor list
        r_cut (float): Default cutoff radius (in distance units).
        r_on (float): Default turn-on radius (in distance units).
        mode (str): energy shifting/smoothing mode.

    `Morse` specifies that a Morse pair potential should be applied between
    every non-excluded particle pair in the simulation.

    .. math::
        :nowrap:

        \\begin{eqnarray*}
        V_{\\mathrm{morse}}(r) = & D_0 \\left[ \\exp \\left(-2\\alpha\\left(
            r-r_0\\right)\\right) -2\\exp \\left(-\\alpha\\left(r-r_0\\right)
            \\right) \\right] & r < r_{\\mathrm{cut}} \\\\
            = & 0 & r \\ge r_{\\mathrm{cut}} \\\\
        \\end{eqnarray*}

    See `Pair` for details on how forces are calculated and the available
    energy shifting and smoothing modes. Use `params` dictionary to set
    potential coefficients. The coefficients must be set per unique pair of
    particle types.

    Attributes:
        params (`TypeParameter` [\
          `tuple` [``particle_type``, ``particle_type``],\
          `dict`]):
          The potential parameters. The dictionary has the following keys:

          * ``D0`` (`float`, **required**) - depth of the potential at its
            minimum :math:`D_0` (in energy units)

          * ``alpha`` (`float`, **required**) - the width of the potential well
            :math:`\\alpha` (in units of 1/distance)

          * ``r0`` (`float`, **required**) - position of the minimum
            :math:`r_0` (in distance units)

    Example::

        nl = nlist.Cell()
        morse = pair.Morse(r_cut=3.0, nlist=nl)
        morse.params[('A', 'A')] = dict(D0=1.0, alpha=3.0, r0=1.0)
        morse.r_cut[('A', 'B')] = 3.0
    """

    _cpp_class_name = "PotentialPairMorse"
    def __init__(self, nlist, r_cut=None, r_on=0., mode='none'):
        super().__init__(nlist, r_cut, r_on, mode)
        params = TypeParameter('params', 'particle_types',
                               TypeParameterDict(D0=float, alpha=float, r0=float,
                                             len_keys=2))
        self._add_typeparam(params)


class DPD(Pair):
    """Dissipative Particle Dynamics.

    Args:
        nlist (`hoomd.md.nlist.NList`): Neighbor list
        kT (`hoomd.variant` or `float`): Temperature of
          thermostat (in energy units).
        seed (int): seed for the PRNG in the DPD thermostat.
        r_cut (float): Default cutoff radius (in distance units).
        r_on (float): Default turn-on radius (in distance units).

    `DPD` specifies that a DPD pair force should be applied between every
    non-excluded particle pair in the simulation, including an interaction
    potential, pairwise drag force, and pairwise random force. See `Groot and
    Warren 1997 <http://dx.doi.org/10.1063/1.474784>`_.

    .. math::
        :nowrap:

        \\begin{eqnarray*}
        F = F_{\\mathrm{C}}(r) + F_{\\mathrm{R,ij}}(r_{ij}) +
        F_{\\mathrm{D,ij}}(v_{ij}) \\\\
        \\end{eqnarray*}

    .. math::
        :nowrap:

        \\begin{eqnarray*}
        F_{\\mathrm{C}}(r) = & A \\cdot  w(r_{ij}) \\\\
        F_{\\mathrm{R, ij}}(r_{ij}) = & - \\theta_{ij}\\sqrt{3}
        \\sqrt{\\frac{2k_b\\gamma T}{\\Delta t}}\\cdot w(r_{ij})  \\\\
        F_{\\mathrm{D, ij}}(r_{ij}) = & - \\gamma w^2(r_{ij})\\left(
        \\hat r_{ij} \\circ v_{ij} \\right)  \\\\
        \\end{eqnarray*}

    .. math::
        :nowrap:

        \\begin{eqnarray*}
        w(r_{ij}) = &\\left( 1 - r/r_{\\mathrm{cut}} \\right)
        & r < r_{\\mathrm{cut}} \\\\
                  = & 0 & r \\ge r_{\\mathrm{cut}} \\\\
        \\end{eqnarray*}

    where :math:`\\hat r_{ij}` is a normalized vector from particle i to
    particle j, :math:`v_{ij} = v_i - v_j`, and :math:`\\theta_{ij}` is a
    uniformly distributed random number in the range [-1, 1].

    `DPD` generates random numbers by hashing together the particle tags in the
    pair, the user seed, and the current time step index.

    Attention:
        Change the seed if you reset the simulation time step to 0. If you keep
        the same seed, the simulation will continue with the same sequence of
        random numbers used previously and may cause unphysical correlations.

        For MPI runs: all ranks other than 0 ignore the seed input and use the
        value of rank 0.

    `C. L. Phillips et. al. 2011 <http://dx.doi.org/10.1016/j.jcp.2011.05.021>`_
    describes the DPD implementation details in HOOMD-blue. Cite it if you
    utilize the DPD functionality in your work.

    `DPD` does not implement and energy shift / smoothing modes due to the
    function of the force. Use `params` dictionary to set potential
    coefficients. The coefficients must be set per unique pair of particle
    types.

    To use the DPD thermostat, an `hoomd.md.methods.NVE` integrator
    must be applied to the system and the user must specify a temperature.  Use
    of the dpd thermostat pair force with other integrators will result in
    unphysical behavior. To use pair.dpd with a different conservative potential
    than :math:`F_C`, set A to zero and define the conservative pair potential
    separately.  Note that DPD thermostats are often defined in terms of
    :math:`\\sigma` where :math:`\\sigma = \\sqrt{2k_b\\gamma T}`.

    Attributes:
        params (`TypeParameter` [\
          `tuple` [``particle_type``, ``particle_type``],\
          `dict`]):
          The force parameters. The dictionary has the following keys:

          * ``A`` (`float`, **required**) - :math:`A` (in force units)

          * ``gamma`` (`float`, **required**) - :math:`\\gamma` (in units of
            force/velocity)

    Example::

        nl = nlist.Cell()
        dpd = pair.DPD(nlist=nl, kT=1.0, seed=0, r_cut=1.0)
        dpd.params[('A', 'A')] = dict(A=25.0, gamma=4.5)
        dpd.params[('A', 'B')] = dict(A=40.0, gamma=4.5)
        dpd.params[('B', 'B')] = dict(A=25.0, gamma=4.5)
        dpd.params[(['A', 'B'], ['C', 'D'])] = dict(A=40.0, gamma=4.5)
    """
    _cpp_class_name = "PotentialPairDPDThermoDPD"
    def __init__(self, nlist, kT, seed=3, r_cut=None, r_on=0., mode='none'):
        super().__init__(nlist, r_cut, r_on, mode)
        params = TypeParameter('params', 'particle_types',
                               TypeParameterDict(A=float, gamma=float, len_keys=2))
        self._add_typeparam(params)

        d = ParameterDict(kT=hoomd.variant.Variant, seed=int)
        self._param_dict.update(d)

        self.kT = kT
        self.seed = seed


class DPDConservative(Pair):
    """DPD Conservative pair force.

    Args:
        nlist (`hoomd.md.nlist.NList`): Neighbor list
        r_cut (float): Default cutoff radius (in distance units).
        r_on (float): Default turn-on radius (in distance units).

    `DPDConservative` specifies the conservative part of the DPD pair potential
    should be applied between every non-excluded particle pair in the
    simulation. No thermostat (e.g. Drag Force and Random Force) is applied, as
    is in `DPD`.

    .. math::
        :nowrap:

        \\begin{eqnarray*}
        V_{\\mathrm{DPD-C}}(r) = & A \\cdot \\left( r_{\\mathrm{cut}} - r
          \\right) - \\frac{1}{2} \\cdot \\frac{A}{r_{\\mathrm{cut}}} \\cdot
          \\left(r_{\\mathrm{cut}}^2 - r^2 \\right)
          & r < r_{\\mathrm{cut}} \\\\
                              = & 0 & r \\ge r_{\\mathrm{cut}} \\\\
        \\end{eqnarray*}


    `DPDConservative` does not implement and energy shift / smoothing modes due
    to the function of the force. Use `params` dictionary to set potential
    coefficients. The coefficients must be set per unique pair of particle
    types.

    Attributes:
        params (`TypeParameter` [\
          `tuple` [``particle_type``, ``particle_type``],\
          `dict`]):
          The potential parameters. The dictionary has the following keys:

          * ``A`` (`float`, **required**) - :math:`A` (in force units)

    Example::

        nl = nlist.Cell()
        dpdc = pair.DPDConservative(nlist=nl, r_cut=3.0)
        dpdc.params[('A', 'A')] = dict(A=1.0)
        dpdc.params[('A', 'B')] = dict(A=2.0, r_cut = 1.0)
        dpdc.params[(['A', 'B'], ['C', 'D'])] = dict(A=3.0)
    """
    _cpp_class_name = "PotentialPairDPD"
    def __init__(self, nlist, r_cut=None, r_on=0., mode='none'):
        # initialize the base class
        super().__init__(nlist, r_cut, r_on, mode)
        params =  TypeParameter('params', 'particle_types',
                                TypeParameterDict(A=float, len_keys=2))
        self._add_typeparam(params)


class DPDLJ(Pair):
    """Dissipative Particle Dynamics with a LJ conservative force.

    Args:
        nlist (`hoomd.md.nlist.NList`): Neighbor list
        kT (`hoomd.variant` or `float`): Temperature of
            thermostat (in energy units).
        seed (int): seed for the PRNG in the DPD thermostat.
        r_cut (float): Default cutoff radius (in distance units).
        r_on (float): Default turn-on radius (in distance units).

    `DPDLJ` specifies that a DPD thermostat and a Lennard-Jones pair potential
    should be applied between every non-excluded particle pair in the
    simulation.

    `C. L. Phillips et. al. 2011 <http://dx.doi.org/10.1016/j.jcp.2011.05.021>`_
    describes the DPD implementation details in HOOMD-blue. Cite it if you
    utilize the DPD functionality in your work.

    .. math::
        :nowrap:

        \\begin{eqnarray*}
        F = F_{\\mathrm{C}}(r) + F_{\\mathrm{R,ij}}(r_{ij}) +
            F_{\\mathrm{D,ij}}(v_{ij}) \\\\
        \\end{eqnarray*}

    .. math::
        :nowrap:

        \\begin{eqnarray*}
        F_{\\mathrm{C}}(r) = & \\partial V_{\\mathrm{LJ}} / \\partial r \\\\
        F_{\\mathrm{R, ij}}(r_{ij}) = & - \\theta_{ij}\\sqrt{3}
            \\sqrt{\\frac{2k_b\\gamma T}{\\Delta t}}\\cdot w(r_{ij})  \\\\
        F_{\\mathrm{D, ij}}(r_{ij}) = & - \\gamma w^2(r_{ij})
            \\left( \\hat r_{ij} \\circ v_{ij} \\right)  \\\\
        \\end{eqnarray*}

    .. math::
        :nowrap:

        \\begin{eqnarray*}
        V_{\\mathrm{LJ}}(r) = & 4 \\varepsilon \\left[ \\left(
            \\frac{\\sigma}{r} \\right)^{12} -
            \\alpha \\left( \\frac{\\sigma}{r} \\right)^{6} \\right]
            & r < r_{\\mathrm{cut}} \\\\
                            = & 0 & r \\ge r_{\\mathrm{cut}} \\\\
        \\end{eqnarray*}

    .. math::
        :nowrap:

        \\begin{eqnarray*}
        w(r_{ij}) = &\\left( 1 - r/r_{\\mathrm{cut}} \\right)
            & r < r_{\\mathrm{cut}} \\\\
                  = & 0 & r \\ge r_{\\mathrm{cut}} \\\\
        \\end{eqnarray*}

    where :math:`\\hat r_{ij}` is a normalized vector from particle i to
    particle j, :math:`v_{ij} = v_i - v_j`, and :math:`\\theta_{ij}` is a
    uniformly distributed random number in the range [-1, 1].

    Use `params` dictionary to set potential coefficients. The coefficients must
    be set per unique pair of particle types.

    To use the DPD thermostat, an `hoomd.md.methods.NVE` integrator
    must be applied to the system and the user must specify a temperature.  Use
    of the dpd thermostat pair force with other integrators will result in
    unphysical behavior.

    Attributes:
        params (`TypeParameter` [\
          `tuple` [``particle_type``, ``particle_type``],\
          `dict`]):
          The DPDLJ potential parameters. The dictionary has the following keys:

          * ``epsilon`` (`float`, **required**) - :math:`\\varepsilon`
            (in energy units)

          * ``sigma`` (`float`, **required**) - :math:`\\sigma`
            (in distance units)

          * ``alpha`` (`float`, **optional**, defaults to 1.0) -
            :math:`\\alpha` (unitless)

          * ``gamma`` (`float`, **required**) - :math:`\\gamma` (in units of
            force/velocity)

    Example::

        nl = nlist.Cell()
        dpdlj = pair.DPDLJ(nlist=nl, kT=1.0, seed=0, r_cut=2.5)
        dpdlj.params[('A', 'A')] = dict(epsilon=1.0, sigma=1.0, gamma=4.5)
        dpdlj.params[(['A', 'B'], ['C', 'D'])] = dict(epsilon=3.0, sigma=1.0, gamma=1.2)
        dpdlj.r_cut[('B', 'B')] = 2.0**(1.0/6.0)
    """
    _cpp_class_name = "PotentialPairDPDLJThermoDPD"
    def __init__(self, nlist, kT, seed=3, r_cut=None, r_on=0., mode='none'):
        if mode == 'xplor':
            raise ValueError("xplor smoothing is not supported with pair.DPDLJ")

        super().__init__(nlist, r_cut, r_on, mode)
        params = TypeParameter('params', 'particle_types', TypeParameterDict(
            epsilon=float, sigma=float, alpha=1.0, gamma=float,
            len_keys=2))
        self._add_typeparam(params)

        d = ParameterDict(kT=hoomd.variant.Variant, seed=int,
                          mode=OnlyFrom(['none', 'shift']))
        self._param_dict.update(d)

        self.kT = kT
        self.seed = seed
        self.mode = mode


class ForceShiftedLJ(Pair):
    """Force-shifted Lennard-Jones pair potential.

    Args:
        nlist (`hoomd.md.nlist.NList`): Neighbor list
        r_cut (float): Default cutoff radius (in distance units).
        r_on (float): Default turn-on radius (in distance units).
        mode (str): energy shifting/smoothing mode.

    `ForceShiftedLJ` specifies that a modified Lennard-Jones pair force should
    be applied between non-excluded particle pair in the simulation. The force
    differs from the one calculated by  `LJ` by the subtraction of the
    value of the force at :math:`r_{\\mathrm{cut}}`, such that the force
    smoothly goes to zero at the cut-off. The potential is modified by a linear
    function. This potential can be used as a substitute for `LJ`,
    when the exact analytical form of the latter is not required but a smaller
    cut-off radius is desired for computational efficiency. See `Toxvaerd et.
    al. 2011 <http://dx.doi.org/10.1063/1.3558787>`_ for a discussion of this
    potential.

    .. math::
        :nowrap:

        \\begin{eqnarray*}
        V(r) = & 4 \\varepsilon \\left[ \\left( \\frac{\\sigma}{r}
          \\right)^{12} - \\alpha \\left( \\frac{\\sigma}{r} \\right)^{6}
          \\right] + \\Delta V(r) & r < r_{\\mathrm{cut}}\\\\
             = & 0 & r \\ge r_{\\mathrm{cut}} \\\\
        \\end{eqnarray*}

    .. math::

        \\Delta V(r) = -(r - r_{\\mathrm{cut}}) \\frac{\\partial
          V_{\\mathrm{LJ}}}{\\partial r}(r_{\\mathrm{cut}})

    See `Pair` for details on how forces are calculated and the
    available energy shifting and smoothing modes. Use `params` dictionary to
    set potential coefficients. The coefficients must be set per unique pair of
    particle types.

    Attributes:
        params (`TypeParameter` [\
          `tuple` [``particle_type``, ``particle_type``],\
          `dict`]):
          The potential parameters. The dictionary has the following keys:

          * ``epsilon`` (`float`, **required**) - :math:`\\varepsilon`
            (in energy units)

          * ``sigma`` (`float`, **required**) - :math:`\\sigma`
            (in distance units)

          * ``alpha`` (`float`, **optional**, defaults to 1.0) - :math:`\\alpha`
            (unitless)

    Example::

        nl = nlist.Cell()
        fslj = pair.ForceShiftedLJ(nlist=nl, r_cut=1.5)
        fslj.params[('A', 'A')] = dict(epsilon=1.0, sigma=1.0)
    """
    _cpp_class_name = "PotentialPairForceShiftedLJ"
    def __init__(self, nlist, r_cut=None, r_on=0., mode='none'):
        # initialize the base class
        super().__init__(nlist, r_cut, r_on, mode)

        params = TypeParameter('params', 'particle_types',
                               TypeParameterDict(sigma=float, epsilon=float,
                                                 len_keys=2))
        self._add_typeparam(params)


class Moliere(Pair):
    """Moliere pair potential.

    Args:
        nlist (`hoomd.md.nlist.NList`): Neighbor list
        r_cut (float): Default cutoff radius (in distance units).
        r_on (float): Default turn-on radius (in distance units).
        mode (str): energy shifting/smoothing mode.

    `Moliere` specifies that a Moliere type pair potential should be applied
    between every non-excluded particle pair in the simulation.

    .. math::
        :nowrap:

        \\begin{eqnarray*}
        V_{\\mathrm{Moliere}}(r)
          = & \\frac{Z_i Z_j e^2}{4 \\pi \\epsilon_0 r_{ij}} \\left[ 0.35 \\exp
          \\left( -0.3 \\frac{r_{ij}}{a_F} \\right) + \\\\
          0.55 \\exp \\left( -1.2 \\frac{r_{ij}}{a_F} \\right) + 0.10 \\exp
          \\left( -6.0 \\frac{r_{ij}}{a_F} \\right) \\right]
          & r < r_{\\mathrm{cut}} \\\\
          = & 0 & r > r_{\\mathrm{cut}} \\\\
        \\end{eqnarray*}

    Where each parameter is defined as:

    - :math:`Z_i` - *Z_i* - Atomic number of species i (unitless)
    - :math:`Z_j` - *Z_j* - Atomic number of species j (unitless)
    - :math:`e` - *elementary_charge* - The elementary charge (in charge units)
    - :math:`a_F = \\frac{0.8853 a_0}{\\left( \\sqrt{Z_i} + \\sqrt{Z_j}
      \\right)^{2/3}}`, where :math:`a_0` is the Bohr radius (in distance units)

    See `Pair` for details on how forces are calculated and the available
    energy shifting and smoothing modes. Use `params` dictionary to set
    potential coefficients. The coefficients must be set per unique pair of
    particle types.

    Attributes:
        params (`TypeParameter` [\
          `tuple` [``particle_type``, ``particle_type``],\
          `dict`]):
          The potential parameters. The dictionary has the following keys:

          * ``qi`` (`float`, **required**) -
            :math:`q_i = Z_i \\frac{e}{\\sqrt{4 \\pi \\epsilon_0}}`
            (in charge units)

          * ``qj`` (`float`, **required**) -
            :math:`q_j = Z_j \\frac{e}{\\sqrt{4 \\pi \\epsilon_0}}`
            (in charge units)

          * ``aF`` (`float`, **required**) -
            :math:`a_F = \\frac{0.8853 a_0}{\\left( \\sqrt{Z_i} + \\sqrt{Z_j}
            \\right)^{2/3}}`

    Example::

        nl = nlist.Cell()
        moliere = pair.Moliere(r_cut = 3.0, nlist=nl)

        Zi = 54
        Zj = 7
        e = 1
        a0 = 1
        aF = 0.8853 * a0 / (np.sqrt(Zi) + np.sqrt(Zj))**(2/3)

        moliere.params[('A', 'B')] = dict(qi=Zi*e, qj=Zj*e, aF=aF)
    """
    _cpp_class_name = "PotentialPairMoliere"
    def __init__(self, nlist, r_cut=None, r_on=0., mode='none'):
        super().__init__(nlist, r_cut, r_on, mode)
        params = TypeParameter('params', 'particle_types',
                               TypeParameterDict(qi=float, qj=float, aF=float,
                                                 len_keys=2))
        self._add_typeparam(params)


class ZBL(Pair):
    """ZBL pair potential.

    Args:
        nlist (`hoomd.md.nlist.NList`): Neighbor list
        r_cut (float): Default cutoff radius (in distance units).
        r_on (float): Default turn-on radius (in distance units).
        mode (str): energy shifting/smoothing mode.

    `ZBL` specifies that a Ziegler-Biersack-Littmark pair potential
    should be applied between every non-excluded particle pair in the
    simulation.

    .. math::
        :nowrap:

        \\begin{eqnarray*}
        V_{\\mathrm{ZBL}}(r) =
          & \\frac{Z_i Z_j e^2}{4 \\pi \\epsilon_0 r_{ij}} \\left[ 0.1818
          \\exp \\left( -3.2 \\frac{r_{ij}}{a_F} \\right) \\\\
          + 0.5099 \\exp \\left( -0.9423 \\frac{r_{ij}}{a_F} \\right) \\\\
          + 0.2802 \\exp \\left( -0.4029 \\frac{r_{ij}}{a_F} \\right) \\\\
          + 0.02817 \\exp \\left( -0.2016 \\frac{r_{ij}}{a_F} \\right) \\right],
          & r < r_{\\mathrm{cut}} \\\\
          = & 0, & r > r_{\\mathrm{cut}} \\\\
        \\end{eqnarray*}

    Where each parameter is defined as:

    - :math:`Z_i` - *Z_i* - Atomic number of species i (unitless)
    - :math:`Z_j` - *Z_j* - Atomic number of species j (unitless)
    - :math:`e` - *elementary_charge* - The elementary charge (in charge units)
    - :math:`a_F = \\frac{0.8853 a_0}{ Z_i^{0.23} + Z_j^{0.23} }`, where
      :math:`a_0` is the Bohr radius (in distance units)

    See `Pair` for details on how forces are calculated and the available
    energy shifting and smoothing modes. Use `params` dictionary to set
    potential coefficients.

    Attributes:
        params (`TypeParameter` [\
          `tuple` [``particle_type``, ``particle_type``],\
          dict]):
          The ZBL potential parameters. The dictionary has the following keys:

          * ``q_i`` (`float`, **required**) - :math:`q_i=Z_i \\frac{e}{\\sqrt{4
            \\pi \\epsilon_0}}` (in charge units)

          * ``q_j`` (`float`, **required**) - :math:`q_j=Z_j \\frac{e}{\\sqrt{4
            \\pi \\epsilon_0}}` (in charge units)

          * ``a_F`` (`float`, **required**) -
            :math:`a_F = \\frac{0.8853 a_0}{ Z_i^{0.23} + Z_j^{0.23} }`

    Example::

        nl = nlist.Cell()
        zbl = pair.ZBL(r_cut = 3.0, nlist=nl)

        Zi = 54
        Zj = 7
        e = 1
        a0 = 1
        aF = 0.8853 * a0 / (Zi**(0.23) + Zj**(0.23))

        zbl.params[('A', 'B')] = dict(qi=Zi*e, qj=Zj*e, aF=aF)
    """
    _cpp_class_name = "PotentialPairZBL"
    def __init__(self, nlist, r_cut=None, r_on=0., mode='none'):

        super().__init__(nlist, r_cut, r_on, mode);
        params = TypeParameter('params', 'particle_types',
                               TypeParameterDict(qi=float, qj=float, aF=float,
                                                 len_keys=2))
        self._add_typeparam(params)


class Mie(Pair):
    """Mie pair potential.

    Args:
        nlist (`hoomd.md.nlist.NList`): Neighbor list
        r_cut (float): Default cutoff radius (in distance units).
        r_on (float): Default turn-on radius (in distance units).
        mode (str): energy shifting/smoothing mode.

    `Mie` specifies that a Mie pair potential should be applied between every
    non-excluded particle pair in the simulation.

    .. math::
        :nowrap:

        \\begin{eqnarray*}
        V_{\\mathrm{mie}}(r)
          = & \\left( \\frac{n}{n-m} \\right) {\\left( \\frac{n}{m}
          \\right)}^{\\frac{m}{n-m}} \\varepsilon \\left[ \\left(
          \\frac{\\sigma}{r} \\right)^{n} - \\left( \\frac{\\sigma}{r}
          \\right)^{m} \\right] & r < r_{\\mathrm{cut}} \\\\
          = & 0 & r \\ge r_{\\mathrm{cut}} \\\\
        \\end{eqnarray*}

    `Pair` for details on how forces are calculated and the available energy
    shifting and smoothing modes. Use the `params` dictionary to set potential
    coefficients. The coefficients must be set per unique pair of particle
    types.

    Attributes:
        params (`TypeParameter` [\
          `tuple` [``particle_type``, ``particle_type``],\
          `dict`]):
          The potential parameters. The dictionary has the following keys:

          * ``epsilon`` (`float`, **required**) - :math:`\\varepsilon` (in units
            of energy)

          * ``sigma`` (`float`, **required**) - :math:`\\sigma` (in distance
            units)

          * ``n`` (`float`, **required**) - :math:`n` (unitless)

          * ``m`` (`float`, **required**) - :math:`m` (unitless)

    Example::

        nl = nlist.Cell()
        mie = pair.Mie(nlist=nl, r_cut=3.0)
        mie.params[('A', 'A')] = dict(epsilon=1.0, sigma=1.0, n=12, m=6)
        mie.r_cut[('A', 'A')] = 2**(1.0/6.0)
        mie.r_on[('A', 'A')] = 2.0
        mie.params[(['A', 'B'], ['C', 'D'])] = dict(epsilon=1.5, sigma=2.0)
    """
    _cpp_class_name = "PotentialPairMie"

    def __init__(self, nlist, r_cut=None, r_on=0., mode='none'):

        super().__init__(nlist, r_cut, r_on, mode)
        params = TypeParameter('params', 'particle_types',
                               TypeParameterDict(epsilon=float, sigma=float,
                                                 n=float, m=float, len_keys=2))

        self._add_typeparam(params)


class ReactionField(Pair):
    """Onsager reaction field pair potential.

    Args:
        nlist (`hoomd.md.nlist.NList`): Neighbor list
        r_cut (float): Default cutoff radius (in distance units).
        r_on (float): Default turn-on radius (in distance units).
        mode (str): energy shifting/smoothing mode

    `ReactionField` specifies that an Onsager reaction field pair potential
    should be applied between every non-excluded particle pair in the
    simulation.

    Reaction field electrostatics is an approximation to the screened
    electrostatic interaction, which assumes that the medium can be treated as
    an electrostatic continuum of dielectric constant :math:`\\epsilon_{RF}`
    outside the cutoff sphere of radius :math:`r_{\\mathrm{cut}}`. See: `Barker
    et. al. 1973 <http://dx.doi.org/10.1080/00268977300102101>`_.

    .. math::

       V_{\\mathrm{RF}}(r) = \\varepsilon \\left[ \\frac{1}{r} +
           \\frac{(\\epsilon_{RF}-1) r^2}{(2 \\epsilon_{RF} + 1) r_c^3} \\right]

    By default, the reaction field potential does not require charge or diameter
    to be set. Two parameters, :math:`\\varepsilon` and :math:`\\epsilon_{RF}`
    are needed. If :math:`\\epsilon_{RF}` is specified as zero, it will
    represent infinity.

    If *use_charge* is set to True, the following formula is evaluated instead:

    .. math::

        V_{\\mathrm{RF}}(r) = q_i q_j \\varepsilon \\left[ \\frac{1}{r} +
          \\frac{(\\epsilon_{RF}-1) r^2}{(2 \\epsilon_{RF} + 1) r_c^3} \\right]

    where :math:`q_i` and :math:`q_j` are the charges of the particle pair.

    See `Pair` for details on how forces are calculated and the available
    energy shifting and smoothing modes.  Use the `params` dictionary to set
    potential coefficients. The coefficients must be set per unique pair of
    particle types.

    Attributes:
        params (`TypeParameter` [\
          `tuple` [``particle_type``, ``particle_type``],\
          `dict`]):
          The potential parameters. The dictionary has the following keys:

          * ``epsilon`` (`float`, **required**) - :math:`\\varepsilon` (in units
            of energy*distance)

          * ``eps_rf`` (`float`, **required**) - :math:`\\epsilon_{RF}`
            (dimensionless)

          * ``use_charge`` (`boolean`, **optional**) - evaluate pair potntial
            using particle charges (*default*: False)

    Example::

        nl = nlist.Cell()
        reaction_field = pair.reaction_field(nl, r_cut=3.0)
        reaction_field.params[('A', 'B')] = dict(epsilon=1.0, eps_rf=1.0)
        reaction_field.params[('B', 'B')] = dict(epsilon=1.0, eps_rf=0.0, use_charge=True)
    """
    _cpp_class_name = "PotentialPairReactionField"
    def __init__(self, nlist, r_cut=None, r_on=0., mode='none'):
        super().__init__(nlist, r_cut, r_on, mode)
        params = TypeParameter('params', 'particle_types',
                               TypeParameterDict(epsilon=float, eps_rf=float,
                                                 use_charge=False, len_keys=2))

        self._add_typeparam(params)


class DLVO(Pair):
    """DLVO colloidal interaction

    Args:
        r_cut (float): Default cutoff radius (in distance units).
        nlist (`hoomd.md.nlist.NList`): Neighbor list
        name (str): Name of the force instance.
        d_max (float): Maximum diameter particles in the simulation will have
          (in distance units)

    `DLVO` specifies that a DLVO dispersion and electrostatic interaction should
    be applied between every non-excluded particle pair in the simulation.

    .. math::
        :nowrap:

        \\begin{eqnarray*}
        V_{\\mathrm{DLVO}}(r)  = & - \\frac{A}{6} \\left[
            \\frac{2a_1a_2}{r^2 - (a_1+a_2)^2} +
            \\frac{2a_1a_2}{r^2 - (a_1-a_2)^2} \\\\
            + \\log \\left(
            \\frac{r^2 - (a_1+a_2)^2}{r^2 - (a_1-a_2)^2} \\right) \\right]
            & \\\\
            & + \\frac{a_1 a_2}{a_1+a_2} Z e^{-\\kappa(r - (a_1+a_2))}
            & r < (r_{\\mathrm{cut}} + \\Delta) \\\\
            = & 0 & r \\ge (r_{\\mathrm{cut}} + \\Delta)
        \\end{eqnarray*}

    where :math:`a_i` is the radius of particle :math:`i`, :math:`\\Delta = (d_i
    + d_j)/2` and :math:`d_i` is the diameter of particle :math:`i`.

    The first term corresponds to the attractive van der Waals interaction with
    :math:`A` being the Hamaker constant, the second term to the repulsive
    double-layer interaction between two spherical surfaces with Z proportional
    to the surface electric potential. See Israelachvili 2011, pp. 317.

    The DLVO potential does not need charge, but does need diameter. See
    `SLJ` for an explanation on how diameters are handled in the
    neighbor lists.

    Due to the way that DLVO modifies the cutoff condition, it will not function
    properly with the xplor shifting mode. See `Pair` for details on
    how forces are calculated and the available energy shifting and smoothing
    modes.

    Attributes:
        params (`TypeParameter` [\
          `tuple` [``particle_type``, ``particle_type``],\
          `dict`]):
          The potential parameters. The dictionary has the following keys:

          * ``epsilon`` (`float`, **required**) - :math:`\\varepsilon` (in units
            of energy)

          * ``kappa`` (`float`, **required**) - scaling parameter
            :math:`\\kappa` (in units of 1/distance)

          * ``Z`` (`float`, **required**) - :math:`Z` (in units of 1/distance)

          * ``A`` (`float`, **required**) - :math:`A` (in units of energy)

    Example::

        nl = nlist.cell()
        DLVO.pair_coeff.set('A', 'A', epsilon=1.0, kappa=1.0)
        DLVO.pair_coeff.set('A', 'B', epsilon=2.0, kappa=0.5, r_cut=3.0, r_on=2.0);
        DLVO.pair_coeff.set(['A', 'B'], ['C', 'D'], epsilon=0.5, kappa=3.0)
    """
    _cpp_class_name = "PotentialPairDLVO"
    def __init__(self, nlist, r_cut=None, r_on=0., mode='none'):
        if mode=='xplor':
            raise ValueError("xplor is not a valid mode for the DLVO potential")

        super().__init__(nlist, r_cut, r_on, mode)
        params = TypeParameter('params', 'particle_types',
                               TypeParameterDict(kappa=float, Z=float, A=float,
                                                 len_keys=2)
                               )
        self._add_typeparam(params)

        # mode not allowed to be xplor, so re-do param dict entry without that option
        param_dict = ParameterDict(mode=OnlyFrom(['none','shift']))
        self._param_dict.update(param_dict)
        self.mode = mode

        # this potential needs diameter shifting on
        self._nlist.diameter_shift = True


class Buckingham(Pair):
    """Buckingham pair potential.

    Args:
        nlist (`hoomd.md.nlist.NList`): Neighbor list
        r_cut (float): Default cutoff radius (in distance units).
        r_on (float): Default turn-on radius (in distance units).
        mode (str): energy shifting/smoothing mode

    `Buckingham` specifies that a Buckingham pair potential should be applied
    between every non-excluded particle pair in the simulation.

    .. math::
        :nowrap:

        \\begin{eqnarray*}
        V_{\\mathrm{Buckingham}}(r) = & A \\exp\\left(-\\frac{r}{\\rho}\\right)
          - \\frac{C}{r^6} & r < r_{\\mathrm{cut}} \\\\
          = & 0 & r \\ge r_{\\mathrm{cut}} \\\\
        \\end{eqnarray*}

    See `Pair` for details on how forces are calculated and the available
    energy shifting and smoothing modes.  Use the `params` dictionary to set
    potential coefficients.

    Attributes:
        params (`TypeParameter` [\
          `tuple` [``particle_type``, ``particle_type``],\
          `dict`]):
          The potential parameters. The dictionary has the following keys:

          * ``A`` (`float`, **required**) - :math:`A` (in energy units)

          * ``rho`` (`float`, **required**) - :math:`\\rho` (in distance units)

          * ``C`` (`float`, **required**) - :math:`C` (in energy units)

    Example::

        nl = nlist.Cell()
        buck = pair.Buckingham(nl, r_cut=3.0)
        buck.params[('A', 'A')] = {'A': 2.0, 'rho'=0.5, 'C': 1.0}
        buck.params[('A', 'B')] = dict(A=1.0, rho=1.0, C=1.0)
        buck.params[('B', 'B')] = dict(A=2.0, rho=2.0, C=2.0)
    """

    _cpp_class_name = "PotentialPairBuckingham"
    def __init__(self, nlist, r_cut=None, r_on=0., mode='none'):
        super().__init__(nlist, r_cut, r_on, mode)
        params = TypeParameter('params', 'particle_types',
                               TypeParameterDict(A=float, rho=float, C=float,
                                                 len_keys=2))
        self._add_typeparam(params)


class LJ1208(Pair):
    """Lennard-Jones 12-8 pair potential.

    Args:
        nlist (`hoomd.md.nlist.NList`): Neighbor list
        r_cut (float): Default cutoff radius (in distance units).
        r_on (float): Default turn-on radius (in distance units).
        mode (str): energy shifting/smoothing mode

    `LJ1208` specifies that a Lennard-Jones 12-8 pair potential should be
    applied between every non-excluded particle pair in the simulation.

    .. math::
        :nowrap:

        \\begin{eqnarray*}
        V_{\\mathrm{LJ}}(r)
          = & 4 \\varepsilon \\left[ \\left( \\frac{\\sigma}{r} \\right)^{12} -
          \\alpha \\left( \\frac{\\sigma}{r} \\right)^{8} \\right]
          & r < r_{\\mathrm{cut}} \\\\
          = & 0 & r \\ge r_{\\mathrm{cut}} \\\\
        \\end{eqnarray*}

    See `Pair` for details on how forces are calculated and the available
    energy shifting and smoothing modes.  Use the `params` dictionary to set
    potential coefficients.

    Attributes:
        params (`TypeParameter` [\
          `tuple` [``particle_type``, ``particle_type``],\
          `dict`]):
          The potential parameters. The dictionary has the following keys:

          * ``epsilon`` (`float`, **required**) - energy parameter
            :math:`\\varepsilon` (in energy units)

          * ``sigma`` (`float`, **required**) - particle size :math:`\\sigma`
            (in distance units)

    Example::

        nl = nlist.Cell()
        lj1208 = pair.LJ1208(nl, r_cut=3.0)
        lj1208.params[('A', 'A')] = {'sigma': 1.0, 'epsilon': 1.0}
        lj1208.params[('A', 'B')] = dict(epsilon=2.0, sigma=1.0)
    """
    _cpp_class_name = "PotentialPairLJ1208"
    def __init__(self, nlist, r_cut=None, r_on=0., mode='none'):
        super().__init__(nlist, r_cut, r_on, mode);
        params = TypeParameter('params', 'particle_types',
                               TypeParameterDict(epsilon=float, sigma=float,
                                                 len_keys=2))
        self._add_typeparam(params)


class Fourier(Pair):
    """Fourier pair potential.

    Args:
        nlist (`hoomd.md.nlist.NList`): Neighbor list
        r_cut (float): Default cutoff radius (in distance units).
        r_on (float): Default turn-on radius (in distance units).
        mode (str): Energy shifting mode.

    `Fourier` specifies that a Fourier pair potential should be applied between
    every non-excluded particle pair in the simulation.

    .. math::
        :nowrap:

        \\begin{eqnarray*}
        V_{\\mathrm{Fourier}}(r)
          = & \\frac{1}{r^{12}} + \\frac{1}{r^2}\\sum_{n=1}^4
          [a_n cos(\\frac{n \\pi r}{r_{cut}}) +
          b_n sin(\\frac{n \\pi r}{r_{cut}})]
          & r < r_{\\mathrm{cut}}  \\\\
          = & 0 & r \\ge r_{\\mathrm{cut}} \\\\
        \\end{eqnarray*}

        where:
        \\begin{eqnarray*}
        a_1 = \\sum_{n=2}^4 (-1)^n a_n
        \\end{eqnarray*}

        \\begin{eqnarray*}
        b_1 = \\sum_{n=2}^4 n (-1)^n b_n
        \\end{eqnarray*}

        is calculated to enforce close to zero value at r_cut.

    See `Pair` for details on how forces are calculated and the available
    energy shifting and smoothing modes. Use `params` dictionary to set
    potential coefficients. The coefficients must be set per unique pair of
    particle types.

    Attributes:
        params (`TypeParameter` [\
          `tuple` [``particle_type``, ``particle_type``],\
          `dict`]):
          The Fourier potential parameters. The dictionary has the following keys:

          * ``a`` (`float`, **required**) - array of 3 values corresponding to
            a2, a3 and a4 in the Fourier series, unitless)
          * ``b`` (`float`, **required**) - array of 3 values corresponding to
            b2, b3 and b4 in the Fourier series, unitless)

    Example::

        nl = nlist.Cell()
        fourier = pair.Fourier(r_cut=3.0, nlist=nl)
        fourier.params[('A', 'A')] = dict(a=[a2,a3,a4], b=[b2,b3,b4])
    """
    _cpp_class_name = "PotentialPairFourier"
    def __init__(self, nlist, r_cut=None, r_on=0., mode='none'):
        super().__init__(nlist, r_cut, r_on, mode)
        params = TypeParameter('params', 'particle_types',
            TypeParameterDict(a=list, b=list,
            _defaults=dict(a=[float]*3, b=[float]*3), len_keys=2))
        self._add_typeparam(params)


class OPP(Pair):
    """Oscillating pair potential.

    Args:
        nlist (:py:mod:`hoomd.md.nlist.NList`): Neighbor list
        r_cut (float): Default cutoff radius (in distance units).
        r_on (float): Default turn-on radius (in distance units).
        mode (str): energy shifting/smoothing mode

    `OPP` specifies that an oscillating pair potential should be applied between
    every non-excluded particle pair in the simulation. The OPP potential can
    be used to model metallic interactions.

    .. math::
        :nowrap:

        \\begin{equation*}
        V_{\\mathrm{OPP}}(r) = C_1 r^{-\\eta_1}
            + C_2 r^{-\\eta_2} \\cos{\\left(k r - \\phi\\right)}
        \\end{equation*}

    See `Pair` for details on how forces are calculated and the available energy
    shifting and smoothing modes.  Use `params` dictionary to set potential
    coefficients. The coefficients must be set per unique pair of particle
    types.

    The potential comes from
    `Marek Mihalkovič and C. L. Henley 2012 <https://dx.doi.org/10.1103/PhysRevB.85.092102>`_.

    Attributes:
        params (`TypeParameter` [\
            `tuple` [``particle_type``, ``particle_type``],\
            `dict`]):
            The OPP potential parameters. The dictionary has the following keys:

            * ``C1`` (`float`, **required**) -
              Energy scale of the first term :math:`C_1` (energy units)

            * ``C2`` (`float`, **required**) -
              Energy scale of the second term :math:`C_2` (energy units)

            * ``eta1`` (`float`, **required**) -
              The inverse power to take :math:`r` to in the first term,
              :math:`\\eta_1` (unitless).

            * ``eta2`` (`float`, **required**) -
              The inverse power to take :math:`r` to in the second term
              :math:`\\eta_2` (unitless).

            * ``k`` (`float`, **required**) -
              oscillation frequency :math:`k` (inverse distance units)

            * ``phi`` (`float`, **required**) -
              potential phase shift :math:`\\phi` (unitless)

    Example::

        nl = nlist.Cell()
        opp = pair.OPP(nl, r_cut=3.0)
        opp.params[('A', 'A')] = {
            'C1': 1., 'C2': 1., 'eta1': 15,
            'eta2': 3, 'k': 1.0, 'phi': 3.14}
        opp.r_cut[('A', 'B')] = 3.0
    """
    _cpp_class_name = "PotentialPairOPP"
    def __init__(self, nlist, r_cut=None, r_on=0., mode='none'):
        super().__init__(nlist, r_cut, r_on, mode)
        params = TypeParameter('params', 'particle_types',
                               TypeParameterDict(
                                   C1=float, C2=float, eta1=float, eta2=float,
                                   k=float, phi=float, len_keys=2)
                               )
        self._add_typeparam(params)
