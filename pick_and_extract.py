#! /usr/bin/env python
""" This module is for extracting a spectrum from an 
(optionally interactively chosen) selection of spaxels in a FITS datacube.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Button

import astropy.units as u
from astropy.io import fits
from astropy.wcs import WCS
from astropy.table import Table
from astropy.visualization import simple_norm, quantity_support

quantity_support()


class SpecExtractor(object):
    """ Interactively select spaxels in a FITS datacube and extract a spectrum.
    """

    def __init__(self, fitspath, picker_image=None, sci_extend="SCI",
                 cmap="gist_gray", err_extend="ERR", redshift=0.0, norm=None,
                 celestial_coordinates=False, plot_output=False):
        """ Initialize the thingie
        Parameters:
        ===========
        fitspath :: str
            Path of the FITS file containing the data and error cube.

        Optional parameters:
        ====================
        sci_extend, err_extend :: str
            names in the FITS file of the HDUs containing the flux and error array.

        picker_image :: numpy.ndarray or None
            An array in 2 dimensions of same size as the celestial dimensions
            of the datacube to be extracted. If None, the median of the datacube is
            taken, assuming this to be a good image of the stellar continuum.
            Can be particularly useful if I want to pick pixels where some derived property 
            such as a line ratio or similar, that is not directly visible in the cube,
            stands out.

        cmap :: str or mpl.colors.Colormap
            The colormap used for the picker image. Default is `gist_gray`

        norm :: str or astropy.visualization.mpl_normalize.ImageNormalize
            The image normalization to use for the picker image; by default uses
            `astropy.visualization.simple_norm` to create a normalization with
            a sqrt stretch and the 5th and 95th percentiles of the image array
            as vmin and vmax.

        celestial_coordinates :: bool
            Whether to show sky coordinates instead of pixel coordinates on the picker.
            Defaults to False. I don't use it myself but someone else might like it.

        plot_output :: bool
            Whether to make a quicklook plot of the extracted spectrum when pressing "OK". 
            Defaults to False, but this may change as I use it all the time.

        redshft :: float
            Redshift of the galaxy. Defaults to 0. Not really necessary, but convenient as it 
            will create a restwave array that is not wrong, and insert in the spectrum.
        """
        fitsfile = fits.open(fitspath)
        self.redshift = redshift
        self.cmap = cmap
        head = fitsfile[sci_extend].header
        self.data = fitsfile[sci_extend].data * head["PIXAR_SR"] * u.MJy
        self.errs = fitsfile[err_extend].data * head["PIXAR_SR"] * u.MJy
        self.oned_spec = np.zeros(self.data.shape[0]) * u.MJy
        self.oned_errs = np.zeros(self.data.shape[0]) * u.MJy
        # Build wavelength array
        self.wavedims = WCS(fitsfile[sci_extend]).spectral
        self.obswave = (self.wavedims.all_pix2world(
            np.arange(self.oned_spec.shape[0]).reshape(-1, 1),
            0,
        ) * u.m).to(u.micron).flatten()
        self.restwave = (self.obswave / (1 + self.redshift)).to(u.Angstrom)
        self.plot_output = plot_output
        # Insert or create image to pick from, plus selected mask
        if picker_image is None:
            picker_image = np.nanmedian(self.data, axis=0).data
        self.picker_image = picker_image
        self.selected = np.zeros_like(picker_image).astype(bool)
        # Decide whether to use pixel or sky coordinats on figure
        # (no effect on the picking, just for shows).
        if celestial_coordinates:
            prjctn = WCS(fitsfile[sci_extend].header).celestial
        else:
            prjctn = "rectilinear"
        self._projection = prjctn
        # Set color cuts and stretch for picker image
        if norm is None:
            im_min, im_max = np.nanpercentile(picker_image, (5, 95))
            norm = simple_norm(picker_image, stretch="sqrt", vmin=im_min, vmax=im_max)
        # Finally, build plot.
        self._build_plot()

    def _build_plot(self):
        self.fig = plt.figure()
        self.ax = self.fig.add_subplot(111, projection=self._projection)
        # Add buttons
        axclr = self.fig.add_axes([0.85, 0.75, 0.08, 0.06])
        ax_ok = self.fig.add_axes([0.85, 0.65, 0.08, 0.06])
        self.clrbu = Button(axclr, 'Clear')
        self.ok_bu = Button(ax_ok, 'OK')
        self.clrbu.on_clicked(self._on_clr_button)
        self.ok_bu.on_clicked(self._on_ok_button)
        self.ax.imshow(self.picker_image, origin="lower", picker=True, cmap=self.cmap)
        # Now plot a mask that is initially empty
        self.mask = np.ma.masked_where(~self.selected, np.ones_like(self.picker_image))
        self.maskrender = self.ax.imshow(self.mask, cmap="RdBu", origin="lower")
        self.fig.canvas.mpl_connect('pick_event', self._on_click)
        plt.show()

    # def __call__(self):
    #     self.fig.show()

    def _on_click(self, event):
        me = event.mouseevent
        pixx, pixy = round(me.xdata), round(me.ydata)
        self.mask.mask[pixy, pixx] = not self.mask.mask[pixy, pixx]
        self.selected[pixy, pixx] = not self.selected[pixy, pixx]
        self.maskrender.set_data(self.mask)
        plt.draw()

    def _on_clr_button(self, event):
        self.selected = np.zeros_like(self.picker_image).astype(bool)
        self.mask.mask = ~self.selected
        self.maskrender.set_data(self.mask)
        plt.draw()
        # print("Clear button pushed!")

    def _on_ok_button(self, event):
        print("OK button pressed!")
        spec, errs = extract_spectrum(self.data, self.errs, self.selected)
        self.oned_spec = spec
        self.oned_errs = errs
        if self.plot_output:
            checkfig, checkax = plt.subplots(1, 1)
            checkax.plot(self.restwave, self.oned_spec, drawstyle="steps-mid")
            checkax.fill_between(
                self.restwave, self.oned_errs, color="0.8", step="mid")
            checkfig.show()

    def get_spectrum(self):
        """ Returns the latest extracted spectrum.
        Returns :: Astropy.table.Table 
        """
        outspec = Table(
            [self.obswave, self.restwave, self.oned_spec, self.oned_errs],
            names=["obswave", "restwave", "fnu", "dfnu"],)
        return outspec

    def save_spectrum(self, filepath="output.ecsv", savefmt="ascii.ecsv"):
        outspec = self.get_spectrum()
        outspec.write(filepath, format=savefmt)


def extract_spectrum(datacube, errorcube, mask):
    """ Extracts a spectrum from a FITS datacube and a mask of pixels to extract.
    Returns a simple sum of the spectra in the pixels,
    with the errors summed in quadrature.

    Paramters:
    ==========
    datacube, errorcube :: numpy.ndarrays
        The arracy containing the data and errors.
    mask :: numpy.ndarray
        A Numpy array of boolean type set to True for the pixels
        that should be included in the spectrum, and False elsewhere.
    """
    maskcube = np.broadcast_to(mask, datacube.shape)
    datamasked = datacube * maskcube
    errsmasked = errorcube * maskcube
    outspec = np.nansum(datamasked, axis=(1, 2))
    outerrs = np.sqrt(np.nansum(errsmasked**2, axis=(1, 2)))
    return outspec, outerrs


if __name__ == "__main__":
    print("You ran the file, but nothing happened!")
