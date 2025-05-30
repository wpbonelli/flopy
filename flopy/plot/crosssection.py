import copy
import warnings

import matplotlib.colors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Polygon
from numpy.lib.recfunctions import stack_arrays

from ..utils import geometry, import_optional_dependency
from ..utils.geospatial_utils import GeoSpatialUtil
from . import plotutil
from .plotutil import to_mp7_endpoints, to_mp7_pathlines

warnings.simplefilter("always", PendingDeprecationWarning)


class PlotCrossSection:
    """
    Class to create a cross sectional plot of a model.

    Parameters
    ----------
    ax : matplotlib.pyplot axis
        The plot axis.  If not provided it, plt.gca() will be used.
    model : flopy.modflow object
        flopy model object. (Default is None)
    modelgrid : flopy.discretization.Grid object
        can be a StructuredGrid, VertexGrid, or UnstructuredGrid object
    line : dict
        Dictionary with either "row", "column", or "line" key. If key
        is "row" or "column" key value should be the zero-based row or
        column index for cross-section. If key is "line" value should
        be an array of (x, y) tuples with vertices of cross-section.
        Vertices should be in map coordinates consistent with xul,
        yul, and rotation.
    extent : tuple of floats
        (xmin, xmax, ymin, ymax) will be used to specify axes limits.  If None
        then these will be calculated based on grid, coordinates, and rotation.
    geographic_coords : bool
        boolean flag to allow the user to plot cross-section lines in
        geographic coordinates. If False (default), cross-section is plotted
        as the distance along the cross-section line.
    min_segment_length : float
        minimum width of a grid cell polygon to be plotted. Cells with a
        cross-sectional width less than min_segment_length will be ignored
        and not included in the plot. Default is 1e-02.
    """

    def __init__(
        self,
        model=None,
        modelgrid=None,
        ax=None,
        line=None,
        extent=None,
        geographic_coords=False,
        min_segment_length=1e-02,
    ):
        self.ax = ax
        self.geographic_coords = geographic_coords
        self.model = model

        if modelgrid is not None:
            self.mg = modelgrid

        elif model is not None:
            self.mg = model.modelgrid

        else:
            raise Exception("Cannot find model grid")

        if self.mg.top is None or self.mg.botm is None:
            raise AssertionError("modelgrid top and botm must be defined")

        if not isinstance(line, dict):
            raise AssertionError("A line dictionary must be provided")

        line = {k.lower(): v for k, v in line.items()}

        if len(line) != 1:
            s = (
                "only row, column, or line can be specified in line "
                "dictionary keys specified: "
            )
            for k in line.keys():
                s += f"{k} "
            raise AssertionError(s)

        if ax is None:
            self.ax = plt.gca()
        else:
            self.ax = ax

        onkey = next(iter(line.keys()))
        self.__geographic_xpts = None

        # un-translate model grid into model coordinates
        xcellcenters, ycellcenters = geometry.transform(
            self.mg.xcellcenters,
            self.mg.ycellcenters,
            self.mg.xoffset,
            self.mg.yoffset,
            self.mg.angrot_radians,
            inverse=True,
        )

        xverts, yverts = self.mg.cross_section_vertices

        (
            xverts,
            yverts,
        ) = plotutil.UnstructuredPlotUtilities.irregular_shape_patch(xverts, yverts)

        self.xvertices, self.yvertices = geometry.transform(
            xverts,
            yverts,
            self.mg.xoffset,
            self.mg.yoffset,
            self.mg.angrot_radians,
            inverse=True,
        )

        if onkey in ("row", "column"):
            eps = 1.0e-4
            xedge, yedge = self.mg.xyedges
            if onkey == "row":
                self.direction = "x"
                ycenter = ycellcenters.T[0]
                pts = [
                    (xedge[0] - eps, ycenter[int(line[onkey])]),
                    (xedge[-1] + eps, ycenter[int(line[onkey])]),
                ]
            else:
                self.direction = "y"
                xcenter = xcellcenters[0, :]
                pts = [
                    (xcenter[int(line[onkey])], yedge[0] + eps),
                    (xcenter[int(line[onkey])], yedge[-1] - eps),
                ]
        else:
            ln = line[onkey]

            if not PlotCrossSection._is_valid(ln):
                raise ValueError("Invalid line representation")

            gu = GeoSpatialUtil(ln, shapetype="linestring")
            verts = gu.points
            xp = []
            yp = []
            for [v1, v2] in verts:
                xp.append(v1)
                yp.append(v2)

            xp, yp = self.mg.get_local_coords(xp, yp)
            if np.max(xp) - np.min(xp) > np.max(yp) - np.min(yp):
                # this is x-projection and we should buffer x by small amount
                idx0 = np.argmax(xp)
                idx1 = np.argmin(xp)
                idx2 = np.argmax(yp)
                xp[idx0] += 1e-04
                xp[idx1] -= 1e-04
                yp[idx2] += 1e-03
                self.direction = "x"

            else:
                # this is y-projection and we should buffer y by small amount
                idx0 = np.argmax(yp)
                idx1 = np.argmin(yp)
                idx2 = np.argmax(xp)
                yp[idx0] += 1e-04
                yp[idx1] -= 1e-04
                xp[idx2] += 1e-03
                self.direction = "y"

            pts = list(zip(xp, yp))

        self.pts = np.array(pts)

        self.xypts = plotutil.UnstructuredPlotUtilities.line_intersect_grid(
            self.pts, self.xvertices, self.yvertices
        )

        self.xypts = plotutil.UnstructuredPlotUtilities.filter_line_segments(
            self.xypts, threshold=min_segment_length
        )
        # need to ensure that the ordering of vertices in xypts is correct
        # based on the projection. In certain cases vertices need to be sorted
        # for the specific "projection"
        for node, points in self.xypts.items():
            if self.direction == "y":
                if points[0][-1] < points[1][-1]:
                    points = points[::-1]
            else:
                if points[0][0] > points[1][0]:
                    points = points[::-1]

            self.xypts[node] = points

        if len(self.xypts) < 2:
            if len(next(iter(self.xypts.values()))) < 2:
                s = (
                    "cross-section cannot be created\n."
                    " less than 2 points intersect the model grid\n"
                    f" {len(self.xypts.values()[0])} points"
                    " intersect the grid."
                )
                raise Exception(s)

        if self.geographic_coords:
            # transform back to geographic coordinates
            xypts = {}
            for nn, pt in self.xypts.items():
                xp = [t[0] for t in pt]
                yp = [t[1] for t in pt]
                xp, yp = geometry.transform(
                    xp, yp, self.mg.xoffset, self.mg.yoffset, self.mg.angrot_radians
                )
                xypts[nn] = list(zip(xp, yp))

            self.xypts = xypts

        laycbd = []
        self.ncb = 0
        if self.model is not None:
            if self.model.laycbd is not None:
                laycbd = list(self.model.laycbd)
                self.ncb = np.count_nonzero(laycbd)

        if laycbd:
            self.active = []
            for k in range(self.mg.nlay):
                self.active.append(1)
                if laycbd[k] > 0:
                    self.active.append(0)
            self.active = np.array(self.active, dtype=int)
        else:
            self.active = np.ones(self.mg.nlay, dtype=int)

        self._nlay, self._ncpl, self.ncb = self.mg.cross_section_lay_ncpl_ncb(self.ncb)

        top = self.mg.top.reshape(1, self._ncpl)
        botm = self.mg.botm.reshape(self._nlay + self.ncb, self._ncpl)

        self.elev = np.concatenate((top, botm), axis=0)

        self.idomain = self.mg.idomain
        if self.mg.idomain is None:
            self.idomain = np.ones(botm.shape, dtype=int)

        self.projpts = self.set_zpts(None)
        self.projctr = None

        # Create cross-section extent
        if extent is None:
            self.extent = self.get_extent()
        else:
            self.extent = extent

        # this is actually x or y based on projection
        self.xcenters = [
            np.mean(np.array(v).T[0]) for i, v in sorted(self.projpts.items())
        ]

        self.mean_dx = np.mean(
            np.max(self.xvertices, axis=1) - np.min(self.xvertices, axis=1)
        )
        self.mean_dy = np.mean(
            np.max(self.yvertices, axis=1) - np.min(self.yvertices, axis=1)
        )

        self._polygons = {}

        if model is None:
            self._masked_values = [1e30, -1e30]
        else:
            self._masked_values = [model.hnoflo, model.hdry]

        # Set axis limits
        self._set_axes_limits(self.ax)

    @staticmethod
    def _is_valid(line):
        shapely_geo = import_optional_dependency("shapely.geometry")

        if isinstance(line, (list, tuple, np.ndarray)):
            a = np.array(line)
            if (len(a.shape) < 2 or a.shape[0] < 2) or a.shape[1] != 2:
                return False
        elif not isinstance(line, (geometry.LineString, shapely_geo.LineString)):
            return False

        return True

    @property
    def polygons(self):
        """
        Method to return cached matplotlib polygons for a cross
        section

        Returns
        -------
            dict : [matplotlib.patches.Polygon]
        """
        if not self._polygons:
            for cell, poly in self.projpts.items():
                if len(poly) > 4:
                    # this is the rare multipolygon instance...
                    n = 0
                    p = []
                    polys = []
                    for vn, v in enumerate(poly):
                        if vn == 3 + 4 * n:
                            n += 1
                            p.append(v)
                            polys.append(p)
                            p = []
                        else:
                            p.append(v)
                else:
                    polys = [poly]

                for polygon in polys:
                    verts = plotutil.UnstructuredPlotUtilities.arctan2(
                        np.array(polygon)
                    )

                    if cell not in self._polygons:
                        self._polygons[cell] = [Polygon(verts, closed=True)]
                    else:
                        self._polygons[cell].append(Polygon(verts, closed=True))

        return copy.copy(self._polygons)

    def get_extent(self):
        """
        Get the extent of the rotated and offset grid

        Returns
        -------
        tuple : (xmin, xmax, ymin, ymax)
        """
        xpts = []
        for _, verts in self.projpts.items():
            for v in verts:
                xpts.append(v[0])

        xmin = np.min(xpts)
        xmax = np.max(xpts)

        ymin = np.min(self.elev)
        ymax = np.max(self.elev)

        return xmin, xmax, ymin, ymax

    def _set_axes_limits(self, ax):
        """
        Internal method to set axes limits

        Parameters
        ----------
        ax : matplotlib.pyplot axis
            The plot axis

        Returns
        -------
        ax : matplotlib.pyplot axis object

        """
        if ax.get_autoscale_on():
            ax.set_xlim(self.extent[0], self.extent[1])
            ax.set_ylim(self.extent[2], self.extent[3])
        return ax

    def plot_array(self, a, masked_values=None, head=None, **kwargs):
        """
        Plot a three-dimensional array as a patch collection.

        Parameters
        ----------
        a : numpy.ndarray
            Three-dimensional array to plot.
        masked_values : iterable of floats, ints
            Values to mask.
        head : numpy.ndarray
            Three-dimensional array to set top of patches to the minimum
            of the top of a layer or the head value. Used to create
            patches that conform to water-level elevations.
        **kwargs : dictionary
            keyword arguments passed to matplotlib.collections.PatchCollection

        Returns
        -------
        patches : matplotlib.collections.PatchCollection

        """
        ax = kwargs.pop("ax", self.ax)

        if not isinstance(a, np.ndarray):
            a = np.array(a)

        if a.ndim > 1:
            a = np.ravel(a)

        a = a.astype(float)

        if masked_values is not None:
            self._masked_values.extend(list(masked_values))
        for mval in self._masked_values:
            a = np.ma.masked_values(a, mval)

        if isinstance(head, np.ndarray):
            projpts = self.set_zpts(np.ravel(head))
        else:
            projpts = None

        pc = self.get_grid_patch_collection(a, projpts, **kwargs)
        if pc is not None:
            ax.add_collection(pc)
            ax = self._set_axes_limits(ax)

        return pc

    def plot_surface(self, a, masked_values=None, **kwargs):
        """
        Plot a two- or three-dimensional array as line(s).

        Parameters
        ----------
        a : numpy.ndarray
            Two- or three-dimensional array to plot.
        masked_values : iterable of floats, ints
            Values to mask.
        **kwargs : dictionary
            keyword arguments passed to matplotlib.pyplot.plot

        Returns
        -------
        plot : list containing matplotlib.plot objects
        """
        ax = kwargs.pop("ax", self.ax)

        color = kwargs.pop("color", "b")
        color = kwargs.pop("c", color)

        if not isinstance(a, np.ndarray):
            a = np.array(a)

        if a.ndim > 1:
            a = np.ravel(a)

        a = a.astype(float)

        if a.size % self._ncpl != 0:
            raise AssertionError("Array size must be a multiple of ncpl")

        if masked_values is not None:
            self._masked_values.extend(list(masked_values))
        for mval in self._masked_values:
            a = np.ma.masked_values(a, mval)

        d = {
            i: (np.min(np.array(v).T[0]), np.max(np.array(v).T[0]))
            for i, v in sorted(self.projpts.items())
        }

        surface = []
        for cell, val in d.items():
            if cell >= a.size:
                continue
            elif np.isnan(a[cell]):
                continue
            elif a[cell] is np.ma.masked:
                continue
            else:
                line = ax.plot(d[cell], [a[cell], a[cell]], color=color, **kwargs)
                surface.append(line)

        ax = self._set_axes_limits(ax)

        return surface

    def plot_fill_between(
        self,
        a,
        colors=("blue", "red"),
        masked_values=None,
        head=None,
        **kwargs,
    ):
        """
        Plot a three-dimensional array as lines.

        Parameters
        ----------
        a : numpy.ndarray
            Three-dimensional array to plot.
        colors : list
            matplotlib fill colors, two required
        masked_values : iterable of floats, ints
            Values to mask.
        head : numpy.ndarray
            Three-dimensional array to set top of patches to the minimum
            of the top of a layer or the head value. Used to create
            patches that conform to water-level elevations.
        **kwargs : dictionary
            keyword arguments passed to matplotlib.pyplot.plot

        Returns
        -------
        plot : list containing matplotlib.fillbetween objects

        """
        ax = kwargs.pop("ax", self.ax)
        kwargs["colors"] = colors

        if not isinstance(a, np.ndarray):
            a = np.array(a)

        a = np.ravel(a).astype(float)

        if masked_values is not None:
            self._masked_values.extend(list(masked_values))
        for mval in self._masked_values:
            a = np.ma.masked_values(a, mval)

        if isinstance(head, np.ndarray):
            projpts = self.set_zpts(head)
        else:
            projpts = self.projpts

        pc = self.get_grid_patch_collection(a, projpts, fill_between=True, **kwargs)
        if pc is not None:
            ax.add_collection(pc)
            ax = self._set_axes_limits(ax)

        return pc

    def contour_array(self, a, masked_values=None, head=None, **kwargs):
        """
        Contour a two-dimensional array.

        Parameters
        ----------
        a : numpy.ndarray
            Three-dimensional array to plot.
        masked_values : iterable of floats, ints
            Values to mask.
        head : numpy.ndarray
            Three-dimensional array to set top of patches to the minimum
            of the top of a layer or the head value. Used to create
            patches that conform to water-level elevations.
        **kwargs : dictionary
            keyword arguments passed to matplotlib.pyplot.contour

        Returns
        -------
        contour_set : matplotlib.pyplot.contour

        """
        import matplotlib.tri as tri

        if not isinstance(a, np.ndarray):
            a = np.array(a)

        if a.ndim > 1:
            a = np.ravel(a)

        ax = kwargs.pop("ax", self.ax)

        xcenters = self.xcenters
        plotarray = np.array([a[cell] for cell in sorted(self.projpts)])

        (plotarray, xcenters, zcenters, mplcontour) = (
            self.mg.cross_section_set_contour_arrays(
                plotarray, xcenters, head, self.elev, self.projpts
            )
        )

        if not mplcontour:
            if isinstance(head, np.ndarray):
                zcenters = self.set_zcentergrid(np.ravel(head))
            else:
                zcenters = np.array(
                    [np.mean(np.array(v).T[1]) for i, v in sorted(self.projpts.items())]
                )

        # work around for tri-contour ignore vmin & vmax
        # necessary for the tri-contour NaN issue fix
        if "levels" not in kwargs:
            vmin = kwargs.pop("vmin", np.nanmin(plotarray))
            vmax = kwargs.pop("vmax", np.nanmax(plotarray))
            levels = np.linspace(vmin, vmax, 7)
            kwargs["levels"] = levels

        # workaround for tri-contour nan issue
        plotarray[np.isnan(plotarray)] = -(2**31)
        if masked_values is None:
            masked_values = [-(2**31)]
        else:
            masked_values = list(masked_values)
            if -(2**31) not in masked_values:
                masked_values.append(-(2**31))

        ismasked = None
        if masked_values is not None:
            self._masked_values.extend(list(masked_values))

        for mval in self._masked_values:
            if ismasked is None:
                ismasked = np.isclose(plotarray, mval)
            else:
                t = np.isclose(plotarray, mval)
                ismasked += t

        filled = kwargs.pop("filled", False)
        plot_triplot = kwargs.pop("plot_triplot", False)

        if "extent" in kwargs:
            extent = kwargs.pop("extent")

            idx = (
                (xcenters >= extent[0])
                & (xcenters <= extent[1])
                & (zcenters >= extent[2])
                & (zcenters <= extent[3])
            )
            plotarray = plotarray[idx].flatten()
            xcenters = xcenters[idx].flatten()
            zcenters = zcenters[idx].flatten()

        if mplcontour:
            plotarray = np.ma.masked_array(plotarray, ismasked)
            if filled:
                contour_set = ax.contourf(xcenters, zcenters, plotarray, **kwargs)
            else:
                contour_set = ax.contour(xcenters, zcenters, plotarray, **kwargs)
        else:
            triang = tri.Triangulation(xcenters, zcenters)
            analyze = tri.TriAnalyzer(triang)
            mask = analyze.get_flat_tri_mask(rescale=False)

            if ismasked is not None:
                ismasked = ismasked.flatten()
                mask2 = np.any(
                    np.where(ismasked[triang.triangles], True, False), axis=1
                )
                mask[mask2] = True

            triang.set_mask(mask)

            if filled:
                contour_set = ax.tricontourf(triang, plotarray, **kwargs)
            else:
                contour_set = ax.tricontour(triang, plotarray, **kwargs)

            if plot_triplot:
                ax.triplot(triang, color="black", marker="o", lw=0.75)

        ax = self._set_axes_limits(ax)

        return contour_set

    def plot_inactive(self, ibound=None, color_noflow="black", **kwargs):
        """
        Make a plot of inactive cells.  If not specified, then pull ibound
        from the self.ml

        Parameters
        ----------
        ibound : numpy.ndarray
            ibound array to plot.  (Default is ibound in 'BAS6' package.)

        color_noflow : string
            (Default is 'black')

        Returns
        -------
        quadmesh : matplotlib.collections.QuadMesh

        """
        if ibound is None:
            if self.mg.idomain is None:
                raise AssertionError("An idomain array must be provided")
            else:
                ibound = self.mg.idomain

        plotarray = np.zeros(ibound.shape, dtype=int)
        idx1 = ibound == 0
        plotarray[idx1] = 1
        plotarray = np.ma.masked_equal(plotarray, 0)
        cmap = matplotlib.colors.ListedColormap(["0", color_noflow])
        bounds = [0, 1, 2]
        norm = matplotlib.colors.BoundaryNorm(bounds, cmap.N)
        patches = self.plot_array(plotarray, cmap=cmap, norm=norm, **kwargs)

        return patches

    def plot_ibound(
        self,
        ibound=None,
        color_noflow="black",
        color_ch="blue",
        color_vpt="red",
        head=None,
        **kwargs,
    ):
        """
        Make a plot of ibound.  If not specified, then pull ibound from the
        self.model

        Parameters
        ----------
        ibound : numpy.ndarray
            ibound array to plot.  (Default is ibound in 'BAS6' package.)
        color_noflow : string
            (Default is 'black')
        color_ch : string
            Color for constant heads (Default is 'blue'.)
        head : numpy.ndarray
            Three-dimensional array to set top of patches to the minimum
            of the top of a layer or the head value. Used to create
            patches that conform to water-level elevations.
        **kwargs : dictionary
            keyword arguments passed to matplotlib.collections.PatchCollection

        Returns
        -------
        patches : matplotlib.collections.PatchCollection

        """
        if ibound is None:
            if self.model is not None:
                if self.model.version == "mf6":
                    color_ch = color_vpt

            if self.mg.idomain is None:
                raise AssertionError("Ibound/Idomain array must be provided")

            ibound = self.mg.idomain

        plotarray = np.zeros(ibound.shape, dtype=int)
        idx1 = ibound == 0
        idx2 = ibound < 0
        plotarray[idx1] = 1
        plotarray[idx2] = 2
        plotarray = np.ma.masked_equal(plotarray, 0)
        cmap = matplotlib.colors.ListedColormap(["none", color_noflow, color_ch])
        bounds = [0, 1, 2, 3]
        norm = matplotlib.colors.BoundaryNorm(bounds, cmap.N)
        # mask active cells
        patches = self.plot_array(
            plotarray, masked_values=[0], head=head, cmap=cmap, norm=norm, **kwargs
        )
        return patches

    def plot_grid(self, **kwargs):
        """
        Plot the grid lines.

        Parameters
        ----------
            kwargs : ax, colors.  The remaining kwargs are passed into the
                the LineCollection constructor.

        Returns
        -------
            lc : matplotlib.collections.LineCollection

        """
        ax = kwargs.pop("ax", self.ax)

        col = self.get_grid_line_collection(**kwargs)
        if col is not None:
            ax.add_collection(col)
        return col

    def plot_bc(self, name=None, package=None, kper=0, color=None, head=None, **kwargs):
        """
        Plot boundary conditions locations for a specific boundary
        type from a flopy model

        Parameters
        ----------
        name : string
            Package name string ('WEL', 'GHB', etc.). (Default is None)
        package : flopy.modflow.Modflow package class instance
            flopy package class instance. (Default is None)
        kper : int
            Stress period to plot
        color : string
            matplotlib color string. (Default is None)
        head : numpy.ndarray
            Three-dimensional array (structured grid) or
            Two-dimensional array (vertex grid)
            to set top of patches to the minimum of the top of a\
            layer or the head value. Used to create
            patches that conform to water-level elevations.
        **kwargs : dictionary
            keyword arguments passed to matplotlib.collections.PatchCollection

        Returns
        -------
        patches : matplotlib.collections.PatchCollection

        """
        if "ftype" in kwargs and name is None:
            name = kwargs.pop("ftype")

        # Find package to plot
        if package is not None:
            p = package
        elif self.model is not None:
            if name is None:
                raise Exception("ftype not specified")
            name = name.upper()
            p = self.model.get_package(name)
        else:
            raise Exception("Cannot find package to plot")

        # trap for mf6 'cellid' vs mf2005 'k', 'i', 'j' convention
        if isinstance(p, list) or p.parent.version == "mf6":
            if not isinstance(p, list):
                p = [p]

            idx = np.array([])
            for pp in p:
                if pp.package_type in ("lak", "sfr", "maw", "uzf"):
                    t = plotutil.advanced_package_bc_helper(pp, self.mg, kper)
                else:
                    try:
                        mflist = pp.stress_period_data.array[kper]
                    except Exception as e:
                        raise Exception(f"Not a list-style boundary package: {e!s}")
                    if mflist is None:
                        return

                    t = np.array([list(i) for i in mflist["cellid"]], dtype=int).T

                if len(idx) == 0:
                    idx = np.copy(t)
                else:
                    idx = np.append(idx, t, axis=1)

        else:
            # modflow-2005 structured and unstructured grid
            if p.package_type in ("uzf", "lak"):
                idx = plotutil.advanced_package_bc_helper(p, self.mg, kper)
            else:
                try:
                    mflist = p.stress_period_data[kper]
                except Exception as e:
                    raise Exception(f"Not a list-style boundary package: {e!s}")
                if mflist is None:
                    return
                if len(self.mg.shape) == 3:
                    idx = [mflist["k"], mflist["i"], mflist["j"]]
                else:
                    idx = mflist["node"]

        if len(self.mg.shape) == 3:
            plotarray = np.zeros((self.mg.nlay, self.mg.nrow, self.mg.ncol), dtype=int)
            plotarray[idx[0], idx[1], idx[2]] = 1
        elif len(self.mg.shape) == 2:
            plotarray = np.zeros((self._nlay, self._ncpl), dtype=int)
            plotarray[tuple(idx)] = 1
        else:
            plotarray = np.zeros(self._ncpl, dtype=int)
            idx = idx.flatten()
            plotarray[idx] = 1

        plotarray = np.ma.masked_equal(plotarray, 0)
        if color is None:
            key = name[:3].upper()
            if key in plotutil.bc_color_dict:
                c = plotutil.bc_color_dict[key]
            else:
                c = plotutil.bc_color_dict["default"]
        else:
            c = color
        cmap = matplotlib.colors.ListedColormap(["none", c])
        bounds = [0, 1, 2]
        norm = matplotlib.colors.BoundaryNorm(bounds, cmap.N)
        patches = self.plot_array(
            plotarray, masked_values=[0], head=head, cmap=cmap, norm=norm, **kwargs
        )

        return patches

    def plot_centers(
        self, a=None, s=None, masked_values=None, inactive=False, **kwargs
    ):
        """
        Method to plot cell centers on cross-section using matplotlib
        scatter. This method accepts an optional data array(s) for
        coloring and scaling the cell centers. Cell centers in inactive
        nodes are not plotted by default

        Parameters
        ----------
        a : None, np.ndarray
            optional numpy nd.array of size modelgrid.nnodes
        s : None, float, numpy array
            optional point size parameter
        masked_values : None, iterable
            optional list, tuple, or np array of array (a) values to mask
        inactive : bool
            boolean flag to include inactive cell centers in the plot.
            Default is False
        **kwargs :
            matplotlib ax.scatter() keyword arguments

        Returns
        -------
            matplotlib ax.scatter() object
        """
        ax = kwargs.pop("ax", self.ax)

        projpts = self.projpts
        nodes = list(projpts.keys())
        xcs = self.mg.xcellcenters.ravel()
        ycs = self.mg.ycellcenters.ravel()
        projctr = {}

        if not self.geographic_coords:
            xcs, ycs = geometry.transform(
                xcs,
                ycs,
                self.mg.xoffset,
                self.mg.yoffset,
                self.mg.angrot_radians,
                inverse=True,
            )

            for node, points in self.xypts.items():
                projpt = projpts[node]
                d0 = np.min(np.array(projpt).T[0])

                xc_dist = geometry.project_point_onto_xc_line(
                    points[:2], [xcs[node], ycs[node]], d0=d0, calc_dist=True
                )
                projctr[node] = xc_dist

        else:
            projctr = {}
            for node in nodes:
                if self.direction == "x":
                    projctr[node] = xcs[node]
                else:
                    projctr[node] = ycs[node]

        # pop off any centers that are outside the "visual field"
        #  for a given cross-section.
        removed = {}
        for node, points in projpts.items():
            center = projctr[node]
            points = np.array(points[:2]).T
            if np.min(points[0]) > center or np.max(points[0]) < center:
                removed[node] = (np.min(points[0]), center, np.max(points[0]))
                projctr.pop(node)

        # filter out inactive cells
        if not inactive:
            idomain = self.mg.idomain.ravel()
            for node, points in projpts.items():
                if idomain[node] == 0:
                    if node in projctr:
                        projctr.pop(node)

        self.projctr = projctr
        nodes = list(projctr.keys())
        xcenters = list(projctr.values())
        zcenters = [np.mean(np.array(projpts[node]).T[1]) for node in nodes]

        if a is not None:
            if not isinstance(a, np.ndarray):
                a = np.array(a)
            a = a.ravel().astype(float)

            if masked_values is not None:
                self._masked_values.extend(list(masked_values))

            for mval in self._masked_values:
                a[a == mval] = np.nan

            a = a[nodes]

        if s is not None:
            if not isinstance(s, (int, float)):
                s = s[nodes]
        print(len(xcenters))
        scat = ax.scatter(xcenters, zcenters, c=a, s=s, **kwargs)
        return scat

    def plot_vector(
        self,
        vx,
        vy,
        vz,
        head=None,
        kstep=1,
        hstep=1,
        normalize=False,
        masked_values=None,
        **kwargs,
    ):
        """
        Plot a vector.

        Parameters
        ----------
        vx : np.ndarray
            x component of the vector to be plotted (non-rotated)
            array shape must be (nlay, nrow, ncol) for a structured grid
            array shape must be (nlay, ncpl) for a unstructured grid
        vy : np.ndarray
            y component of the vector to be plotted (non-rotated)
            array shape must be (nlay, nrow, ncol) for a structured grid
            array shape must be (nlay, ncpl) for a unstructured grid
        vz : np.ndarray
            y component of the vector to be plotted (non-rotated)
            array shape must be (nlay, nrow, ncol) for a structured grid
            array shape must be (nlay, ncpl) for a unstructured grid
        head : numpy.ndarray
            MODFLOW's head array.  If not provided, then the quivers will be
            plotted in the cell center.
        kstep : int
            layer frequency to plot (default is 1)
        hstep : int
            horizontal frequency to plot (default is 1)
        normalize : bool
            boolean flag used to determine if vectors should be normalized
            using the vector magnitude in each cell (default is False)
        masked_values : iterable of floats
            values to mask
        kwargs : matplotlib.pyplot keyword arguments for the
            plt.quiver method

        Returns
        -------
        quiver : matplotlib.pyplot.quiver
            result of the quiver function

        """
        ax = kwargs.pop("ax", self.ax)
        pivot = kwargs.pop("pivot", "middle")

        # Check that the cross section is not arbitrary with a tolerance
        # of the mean cell size in each direction
        arbitrary = False
        pts = self.pts
        xuniform = [
            True if abs(pts.T[0, 0] - i) < self.mean_dy else False for i in pts.T[0]
        ]
        yuniform = [
            True if abs(pts.T[1, 0] - i) < self.mean_dx else False for i in pts.T[1]
        ]
        if not np.all(xuniform) and not np.all(yuniform):
            arbitrary = True
        if arbitrary:
            err_msg = (
                "plot_specific_discharge() does not support arbitrary cross-sections"
            )
            raise AssertionError(err_msg)

        # get ibound array to mask inactive cells
        ib = np.ones((self.mg.nnodes,), dtype=int)
        if self.mg.idomain is not None:
            ib = self.mg.idomain.ravel()

        # get the actual values to plot and set xcenters
        if self.direction == "x":
            u_tmp = vx
        else:
            u_tmp = vy * -1.0

        # kstep implementation for vertex grid
        projpts = {
            key: value
            for key, value in self.projpts.items()
            if (key // self._ncpl) % kstep == 0
        }

        # set x and z centers
        if isinstance(head, np.ndarray):
            # pipe kstep to set_zcentergrid to assure consistent array size
            zcenters = self.set_zcentergrid(np.ravel(head), kstep=kstep)

        else:
            zcenters = [np.mean(np.array(v).T[1]) for i, v in sorted(projpts.items())]

        xcenters = np.array(
            [np.mean(np.array(v).T[0]) for i, v in sorted(projpts.items())]
        )

        x = np.ravel(xcenters)
        z = np.ravel(zcenters)
        u = np.array([u_tmp.ravel()[cell] for cell in sorted(projpts)])
        v = np.array([vz.ravel()[cell] for cell in sorted(projpts)])
        ib = np.array([ib[cell] for cell in sorted(projpts)])

        x = x[::hstep]
        z = z[::hstep]
        u = u[::hstep]
        v = v[::hstep]
        ib = ib[::hstep]

        # mask values
        if masked_values is not None:
            for mval in masked_values:
                to_mask = np.logical_or(u == mval, v == mval)
                u[to_mask] = np.nan
                v[to_mask] = np.nan

        # normalize
        if normalize:
            vmag = np.sqrt(u**2.0 + v**2.0)
            idx = vmag > 0.0
            u[idx] /= vmag[idx]
            v[idx] /= vmag[idx]

        # mask with an ibound array
        u[ib == 0] = np.nan
        v[ib == 0] = np.nan

        # plot with quiver
        quiver = ax.quiver(x, z, u, v, pivot=pivot, **kwargs)

        return quiver

    def plot_pathline(self, pl, travel_time=None, method="cell", head=None, **kwargs):
        """
        Plot particle pathlines. Compatible with MODFLOW 6 PRT particle track
        data format, or MODPATH 6 or 7 pathline data format.

        Parameters
        ----------
        pl : list of recarrays or dataframes, or a single recarray or dataframe
            Particle pathline data. If a list of recarrays or dataframes,
            each must contain the path of only a single particle. If just
            one recarray or dataframe, it should contain the paths of all
            particles. The flopy.utils.modpathfile.PathlineFile.get_data()
            or get_alldata() return value may be passed directly as this
            argument.

            For MODPATH 6 or 7 pathlines, columns must include 'x', 'y', 'z',
            'time', 'k', and 'particleid'. Additional columns are ignored.

            For MODFLOW 6 PRT pathlines, columns must include 'x', 'y', 'z',
            't', 'trelease', 'imdl', 'iprp', 'irpt', and 'ilay'. Additional
            columns are ignored. Note that MODFLOW 6 PRT does not assign to
            particles a unique ID, but infers particle identity from 'imdl',
            'iprp', 'irpt', and 'trelease' combos (i.e. via composite key).
        travel_time : float or str
            travel_time is a travel time selection for the displayed
            pathlines. If a float is passed then pathlines with times
            less than or equal to the passed time are plotted. If a
            string is passed a variety logical constraints can be added
            in front of a time value to select pathlines for a select
            period of time. Valid logical constraints are <=, <, ==, >=, and
            >. For example, to select all pathlines less than 10000 days
            travel_time='< 10000' would be passed to plot_pathline.
            (default is None)
        method : str
            "cell" shows only pathlines that intersect with a cell
             "all" projects all pathlines onto the cross section regardless
                of whether they intersect with a given cell
        head : np.ndarray
            optional adjustment to only show pathlines that are <= to
            the top of the water table given a user supplied head array
        kwargs : layer, ax, colors.  The remaining kwargs are passed
            into the LineCollection constructor.

        Returns
        -------
        lc : matplotlib.collections.LineCollection
            The pathlines added to the plot.
        """

        from matplotlib.collections import LineCollection

        # make sure pl is a list
        if not isinstance(pl, list):
            if not isinstance(pl, (np.ndarray, pd.DataFrame)):
                raise TypeError(
                    "Pathline data must be a list of recarrays or dataframes, "
                    f"or a single recarray or dataframe, got {type(pl)}"
                )
            pl = [pl]

        # convert prt to mp7 format
        pl = [
            to_mp7_pathlines(
                p.to_records(index=False) if isinstance(p, pd.DataFrame) else p
            )
            for p in pl
        ]

        # merge pathlines then split on particleid
        pls = stack_arrays(pl, asrecarray=True, usemask=False)
        pids = np.unique(pls["particleid"])
        pl = [pls[pls["particleid"] == pid] for pid in pids]

        # configure plot settings
        marker = kwargs.pop("marker", None)
        markersize = kwargs.pop("markersize", None)
        markersize = kwargs.pop("ms", markersize)
        markercolor = kwargs.pop("markercolor", None)
        markerevery = kwargs.pop("markerevery", 1)
        ax = kwargs.pop("ax", self.ax)
        if "colors" not in kwargs:
            kwargs["colors"] = "0.5"

        projpts = self.projpts
        if head is not None:
            projpts = self.set_zpts(head)

        pl2 = []
        for p in pl:
            tp = plotutil.filter_modpath_by_travel_time(p, travel_time)
            pl2.append(tp)

        tp = plotutil.intersect_modpath_with_crosssection(
            pl2,
            projpts,
            self.xvertices,
            self.yvertices,
            self.direction,
            self._ncpl,
            method=method,
        )
        plines = plotutil.reproject_modpath_to_crosssection(
            tp,
            projpts,
            self.xypts,
            self.direction,
            self.mg,
            self._ncpl,
            self.geographic_coords,
        )

        # build linecollection and markers arrays
        linecol = []
        markers = []
        for _, arr in plines.items():
            arr = np.array(arr)
            # sort by travel time
            arr = arr[arr[:, -1].argsort()]
            linecol.append(arr[:, :-1])
            if marker is not None:
                for xy in arr[::markerevery]:
                    markers.append(xy)

        lc = None
        if len(linecol) > 0:
            lc = LineCollection(linecol, **kwargs)
            ax.add_collection(lc)
            if marker is not None:
                markers = np.array(markers)
                ax.plot(
                    markers[:, 0],
                    markers[:, 1],
                    lw=0,
                    marker=marker,
                    color=markercolor,
                    ms=markersize,
                )

        return lc

    def plot_timeseries(self, ts, travel_time=None, method="cell", head=None, **kwargs):
        """
        Plot the MODPATH timeseries. Not compatible with MODFLOW 6 PRT.

        Parameters
        ----------
        ts : list of rec arrays or a single rec array
            rec array or list of rec arrays is data returned from
            modpathfile TimeseriesFile get_data() or get_alldata()
            methods. Data in rec array is 'x', 'y', 'z', 'time',
            'k', and 'particleid'.
        travel_time : float or str
            travel_time is a travel time selection for the displayed
            pathlines. If a float is passed then pathlines with times
            less than or equal to the passed time are plotted. If a
            string is passed a variety logical constraints can be added
            in front of a time value to select pathlines for a select
            period of time. Valid logical constraints are <=, <, ==, >=, and
            >. For example, to select all pathlines less than 10000 days
            travel_time='< 10000' would be passed to plot_pathline.
            (default is None)
        kwargs : layer, ax, colors.  The remaining kwargs are passed
            into the LineCollection constructor. If layer='all',
            pathlines are output for all layers

        Returns
        -------
            lo : list of Line2D objects
        """
        if "color" in kwargs:
            kwargs["markercolor"] = kwargs["color"]

        return self.plot_pathline(
            ts, travel_time=travel_time, method=method, head=head, **kwargs
        )

    def plot_endpoint(
        self,
        ep,
        direction="ending",
        selection=None,
        selection_direction=None,
        method="cell",
        head=None,
        **kwargs,
    ):
        """
        Plot particle endpoints. Compatible with MODFLOW 6 PRT particle
        track data format, or MODPATH 6 or 7 endpoint data format.

        Parameters
        ----------
        ep : recarray or dataframe
            A numpy recarray with the endpoint particle data from the
            MODPATH endpoint file.

            For MODFLOW 6 PRT pathlines, columns must include 'x', 'y', 'z',
            't', 'trelease', 'imdl', 'iprp', 'irpt', and 'ilay'. Additional
            columns are ignored. Note that MODFLOW 6 PRT does not assign to
            particles a unique ID, but infers particle identity from 'imdl',
            'iprp', 'irpt', and 'trelease' combos (i.e. via composite key).
        direction : str
            String defining if starting or ending particle locations should be
            considered. (default is 'ending')
        selection : tuple
            tuple that defines the zero-base layer, row, column location
            (l, r, c) to use to make a selection of particle endpoints.
            The selection could be a well location to determine capture zone
            for the well. If selection is None, all particle endpoints for
            the user-sepcified direction will be plotted. (default is None)
        selection_direction : str
            String defining is a selection should be made on starting or
            ending particle locations. If selection is not None and
            selection_direction is None, the selection direction will be set
            to the opposite of direction. (default is None)

        kwargs : ax, c, s or size, colorbar, colorbar_label, shrink. The
            remaining kwargs are passed into the matplotlib scatter
            method. If colorbar is True a colorbar will be added to the plot.
            If colorbar_label is passed in and colorbar is True then
            colorbar_label will be passed to the colorbar set_label()
            method. If shrink is passed in and colorbar is True then
            the colorbar size will be set using shrink.

        Returns
        -------
        sp : matplotlib.collections.PathCollection
            The PathCollection added to the plot.
        """

        # convert ep to recarray if needed
        if isinstance(ep, pd.DataFrame):
            ep = ep.to_records(index=False)

        # convert ep from prt to mp7 format if needed
        if "t" in ep.dtype.names:
            from .plotutil import to_mp7_endpoints

            ep = to_mp7_endpoints(ep)

        # configure plot settings
        ax = kwargs.pop("ax", self.ax)
        createcb = kwargs.pop("colorbar", False)
        colorbar_label = kwargs.pop("colorbar_label", "Endpoint Time")
        shrink = float(kwargs.pop("shrink", 1.0))
        s = kwargs.pop("s", np.sqrt(50))
        s = float(kwargs.pop("size", s)) ** 2.0

        cd = {}
        if "c" not in kwargs:
            vmin, vmax = 1e10, -1e10
            for rec in ep:
                tt = float(rec["time"] - rec["time0"])
                if tt < vmin:
                    vmin = tt
                if tt > vmax:
                    vmax = tt
                cd[int(rec["particleid"])] = tt
            kwargs["vmin"] = vmin
            kwargs["vmax"] = vmax
        else:
            tc = kwargs.pop("c")
            for rec in ep:
                cd[int(rec["praticleid"])] = tc

        tep, istart = plotutil.parse_modpath_selection_options(
            ep, direction, selection, selection_direction
        )[0:2]

        projpts = self.projpts
        if head is not None:
            projpts = self.set_zpts(head)

        tep = plotutil.intersect_modpath_with_crosssection(
            tep,
            projpts,
            self.xvertices,
            self.yvertices,
            self.direction,
            self._ncpl,
            method=method,
            starting=istart,
        )
        if not tep:
            return

        epdict = plotutil.reproject_modpath_to_crosssection(
            tep,
            projpts,
            self.xypts,
            self.direction,
            self.mg,
            self._ncpl,
            self.geographic_coords,
            starting=istart,
        )

        arr = []
        c = []
        for node, epl in sorted(epdict.items()):
            for xy in epl:
                c.append(cd[node])
                arr.append(xy)

        arr = np.array(arr)
        sp = ax.scatter(arr[:, 0], arr[:, 1], c=c, s=s, **kwargs)

        # add a colorbar for travel times
        if createcb:
            cb = plt.colorbar(sp, ax=ax, shrink=shrink)
            cb.set_label(colorbar_label)
        return sp

    def get_grid_line_collection(self, **kwargs):
        """
        Get a PatchCollection of the grid

        Parameters
        ----------
        **kwargs : dictionary
            keyword arguments passed to matplotlib.collections.LineCollection

        Returns
        -------
        PatchCollection : matplotlib.collections.LineCollection
        """
        from matplotlib.collections import PatchCollection

        edgecolor = kwargs.pop("colors", "grey")
        edgecolor = kwargs.pop("color", edgecolor)
        edgecolor = kwargs.pop("ec", edgecolor)
        edgecolor = kwargs.pop("edgecolor", edgecolor)
        facecolor = kwargs.pop("facecolor", "none")
        facecolor = kwargs.pop("fc", facecolor)

        polygons = [p for _, polys in sorted(self.polygons.items()) for p in polys]
        if len(polygons) > 0:
            patches = PatchCollection(
                polygons, edgecolor=edgecolor, facecolor=facecolor, **kwargs
            )
        else:
            patches = None

        return patches

    def set_zpts(self, vs):
        """
        Get an array of projected vertices corrected with corrected
        elevations based on minimum of cell elevation (self.elev) or
        passed vs numpy.ndarray

        Parameters
        ----------
        vs : numpy.ndarray
            Two-dimensional array to plot.

        Returns
        -------
        zpts : dict

        """
        # make vertex array based on projection direction
        if vs is not None:
            if not isinstance(vs, np.ndarray):
                vs = np.array(vs)

        if self.direction == "x":
            xyix = 0
        else:
            xyix = -1

        projpts = {}

        nlay = self.mg.nlay + self.ncb

        nodeskip = self.mg.cross_section_nodeskip(nlay, self.xypts)

        cbcnt = 0
        for k in range(1, nlay + 1):
            if not self.active[k - 1]:
                cbcnt += 1
                continue

            k, ns, ncbnn = self.mg.cross_section_adjust_indicies(k - 1, cbcnt)
            top = self.elev[k - 1, :]
            botm = self.elev[k, :]
            d0 = 0

            # trap to split multipolygons
            xypts = []
            for nn, verts in self.xypts.items():
                if nn in nodeskip[ns - 1]:
                    continue

                if len(verts) > 2:
                    i0 = 2
                    for ix in range(len(verts)):
                        if ix == i0 - 1:
                            xypts.append((nn, verts[i0 - 2 : i0]))
                            i0 += 2

                else:
                    xypts.append((nn, verts))

            xypts = sorted(xypts, key=lambda q: q[-1][xyix][xyix])

            if self.direction == "y":
                xypts = xypts[::-1]

            for nn, verts in xypts:
                if vs is None:
                    t = top[nn]
                else:
                    t = vs[nn + ncbnn]
                    if np.isclose(t, -1e30):
                        t = botm[nn]

                    if t < botm[nn]:
                        t = botm[nn]

                    if top[nn] < t:
                        t = top[nn]

                b = botm[nn]
                if self.geographic_coords:
                    if self.direction == "x":
                        projt = [(v[0], t) for v in verts]
                        projb = [(v[0], b) for v in verts]
                    else:
                        projt = [(v[1], t) for v in verts]
                        projb = [(v[1], b) for v in verts]
                else:
                    verts = np.array(verts).T
                    a2 = (np.max(verts[0]) - np.min(verts[0])) ** 2
                    b2 = (np.max(verts[1]) - np.min(verts[1])) ** 2
                    c = np.sqrt(a2 + b2)
                    d1 = d0 + c
                    projt = [(d0, t), (d1, t)]
                    projb = [(d0, b), (d1, b)]
                    d0 += c

                projpt = projt + projb
                node = nn + ncbnn
                if node not in projpts:
                    projpts[node] = projpt
                else:
                    projpts[node] += projpt

        return projpts

    def set_zcentergrid(self, vs, kstep=1):
        """
        Get an array of z elevations at the center of a cell that is based
        on minimum of cell top elevation (self.elev) or passed vs numpy.ndarray

        Parameters
        ----------
        vs : numpy.ndarray
            Three-dimensional array to plot.
        kstep : int
            plotting layer interval

        Returns
        -------
        zcentergrid : numpy.ndarray

        """
        verts = self.set_zpts(vs)
        zcenters = [
            np.mean(np.array(v).T[1])
            for i, v in sorted(verts.items())
            if (i // self._ncpl) % kstep == 0
        ]
        return zcenters

    def get_grid_patch_collection(
        self, plotarray, projpts=None, fill_between=False, **kwargs
    ):
        """
        Get a PatchCollection of plotarray in unmasked cells

        Parameters
        ----------
        plotarray : numpy.ndarray
            One-dimensional array to attach to the Patch Collection.
        projpts : dict
            dictionary defined by node number which contains model
            patch vertices.
        fill_between : bool
            flag to create polygons that mimic the matplotlib fill between
            method. Only used by the plot_fill_between method.
        **kwargs : dictionary
            keyword arguments passed to matplotlib.collections.PatchCollection

        Returns
        -------
        patches : matplotlib.collections.PatchCollection

        """
        from matplotlib.collections import PatchCollection
        from matplotlib.patches import Polygon

        use_cache = False
        if projpts is None:
            use_cache = True
            projpts = self.polygons

        vmin = kwargs.pop("vmin", None)
        vmax = kwargs.pop("vmax", None)

        match_original = False
        if fill_between:
            match_original = True
            colors = kwargs.pop("colors")

        rectcol = []
        data = []
        for cell, poly in sorted(projpts.items()):
            if not use_cache:
                if len(poly) > 4:
                    # multipolygon instance...
                    n = 0
                    p = []
                    polys = []
                    for vn, v in enumerate(poly):
                        if vn == 3 + 4 * n:
                            n += 1
                            p.append(v)
                            polys.append(p)
                            p = []
                        else:
                            p.append(v)
                else:
                    polys = [poly]
            else:
                polys = poly

            for polygon in polys:
                if not use_cache:
                    polygon = plotutil.UnstructuredPlotUtilities.arctan2(
                        np.array(polygon)
                    )

                if np.isnan(plotarray[cell]):
                    continue
                elif plotarray[cell] is np.ma.masked:
                    continue

                if use_cache:
                    rectcol.append(polygon)

                elif fill_between:
                    x = list(set(np.array(polygon).T[0]))
                    y1 = np.max(np.array(polygon).T[1])
                    y = np.min(np.array(polygon).T[1])
                    v = plotarray[cell]

                    if v > y1:
                        v = y

                    if v < y:
                        v = y

                    p1 = [(x[0], y1), (x[1], y1), (x[1], v), (x[0], v)]
                    p2 = [(x[0], v), (x[1], v), (x[1], y), (x[0], y)]
                    rectcol.append(Polygon(p1, closed=True, color=colors[0]))
                    rectcol.append(Polygon(p2, closed=True, color=colors[1]))
                else:
                    rectcol.append(Polygon(polygon, closed=True))
                data.append(plotarray[cell])

        if len(rectcol) > 0:
            patches = PatchCollection(rectcol, match_original=match_original, **kwargs)
            if not fill_between:
                patches.set_array(np.array(data))
                patches.set_clim(vmin, vmax)

        else:
            patches = None

        return patches
