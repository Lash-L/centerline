# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import logging
import os

import click
import fiona
from osgeo import gdal, ogr
from shapely.geometry import mapping, shape

from .exceptions import InvalidInputTypeError, TooFewRidgesError
from .geometry import Centerline

# Enable GDAL/OGR exceptions
gdal.UseExceptions()


@click.command()
@click.argument("src", nargs=1, type=click.Path(exists=True))
@click.argument("dst", nargs=1, type=click.Path(exists=False))
@click.option(
    "-d", "--density", default=0.5, help="Border density.", show_default=True
)
def create_centerlines(src, dst, density=0.5):
    """Convert the geometries from the ``src`` file to centerlines in
    the ``dst`` file.

    Use the ``density`` parameter to adjust the level of detail you want
    the centerlines to be produced with.

    Only polygons and multipolygons are converted to centerlines,
    whereas the other geometries are skipped. The polygon's attributes
    are copied to its ``Centerline`` object.

    If the ``density`` factor does not suit the polygon's geometry, the
    ``TooFewRidgesError`` error is logged as a warning. You should try
    readjusting the ``density`` factor and rerun the command.

    :param src: path to the file containing input geometries
    :type src: str
    :param dst: path to the file that will contain the centerlines
    :type dst: str
    :param density: the border density factor that will be used for
        creating centerlines, defaults to 0.5 [m].
    :type density: float, optional
    :return: ``dst`` file is generated
    :rtype: None
    """

    with fiona.Env():
        with fiona.open(src, mode="r") as source_file:
            schema = source_file.schema.copy()
            schema.update({"geometry": "MultiLineString"})
            driver = get_ogr_driver(filepath=dst)
            with fiona.open(
                dst,
                mode="w",
                driver=driver.GetName(),
                schema=schema,
                crs=source_file.crs,
                encoding=source_file.encoding,
            ) as destination_file:
                for record in source_file:
                    geom = record.get("geometry")
                    input_geom = shape(geom)

                    attributes = record.get("properties")
                    try:
                        centerline_obj = Centerline(
                            input_geom=input_geom,
                            interpolation_dist=density,
                            **attributes
                        )
                    except (InvalidInputTypeError, TooFewRidgesError) as error:
                        logging.warning(error)
                        continue

                    centerline_dict = {
                        "geometry": mapping(centerline_obj),
                        "properties": {
                            k: v
                            for k, v in centerline_obj.__dict__.items()
                            if k in attributes.keys()
                        },
                    }

                    destination_file.write(centerline_dict)

    return None


def get_ogr_driver(filepath):
    """
    Get the OGR driver from the provided file extension.

    Args:
        file_extension (str): file extension

    Returns:
        osgeo.ogr.Driver

    Raises:
        ValueError: no driver is found

    """
    filename, file_extension = os.path.splitext(filepath)
    EXTENSION = file_extension[1:]

    ogr_driver_count = ogr.GetDriverCount()
    for idx in range(ogr_driver_count):
        driver = ogr.GetDriver(idx)
        driver_extension = driver.GetMetadataItem(str("DMD_EXTENSION")) or ""
        driver_extensions = driver.GetMetadataItem(str("DMD_EXTENSIONS")) or ""

        if EXTENSION == driver_extension or EXTENSION in driver_extensions:
            return driver

    else:
        msg = "No driver found for the following file extension: {}".format(
            EXTENSION
        )
        raise InvalidInputTypeError(msg)
