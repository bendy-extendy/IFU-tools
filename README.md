# IFU-tools

Various python convenience code to work with (primarily JWST/NIRSpec) IFU data.

## Dependencies and installation

### Dependencies

Python dependencies are:

- **NumPy**
- **Matplotlib**
- **AstropPy**

### Installation

For now, just download the file and place it either in your working directory or
somwehere in you `PYTHON_PATH` (this can be checked in a Linux/Mac/Unix shell
using `echo $PYTHON_PATH`). 


## Pick spaxels and extract a spectrum

The file `pick-and-extract.py` contains the class `ExtractSPectrum`, which
allows one to interactively select spaxels from an IFU datacube, and extract a
combined spectrum from these pixels. 


