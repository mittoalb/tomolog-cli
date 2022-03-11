import os
import json
import uuid
import dropbox
import pathlib

from epics import PV

from tomolog_cli import logging
from tomolog_cli import plots
from tomolog_cli import reads
from tomolog_cli import auth

__author__ = "Viktor Nikitin"
__copyright__ = "Copyright (c) 2022, UChicago Argonne, LLC."
__docformat__ = 'restructuredtext en'
__all__ = ['TomoLog',]

# tmp files to be created in dropbox
FILE_NAME_PROJ  = 'projection_google'
FILE_NAME_RECON = 'reconstruction_google.jpg'

DROPBOX_TOKEN   = os.path.join(str(pathlib.Path.home()), 'tokens', 'dropbox_token.json')
GOOGLE_TOKEN    = os.path.join(str(pathlib.Path.home()), 'tokens', 'google_token.json')

log = logging.getLogger(__name__)

class TomoLog():
    def __init__(self):

        self.snippets  = auth.google(GOOGLE_TOKEN)
        self.dbx = auth.drop_box(DROPBOX_TOKEN)
        
        # hdf file key definitions
        self.full_file_name = 'measurement_sample_full_file_name'
        self.description_1  = 'measurement_sample_description_1'
        self.description_2  = 'measurement_sample_description_2'
        self.description_3  = 'measurement_sample_description_3'
        self.date           = 'process_acquisition_start_date'
        self.energy         = 'measurement_instrument_monochromator_energy'
        self.pixel_size     = 'measurement_instrument_detector_pixel_size'
        self.magnification  = 'measurement_instrument_detection_system_objective_camera_objective'
        self.resolution     = 'measurement_instrument_detection_system_objective_resolution'
        self.exposure_time  = 'measurement_instrument_detector_exposure_time'
        self.angle_step     = 'process_acquisition_rotation_rotation_step'
        self.num_angle      = 'process_acquisition_rotation_num_angles'
        self.data_size      = 'exchange_data'
        self.binning        = 'measurement_instrument_detector_binning_x'

    def run_log(self, args):

        if args.file_name is None:
            args.file_name = PV(args.PV_prefix.get(as_string=True))
        try:
            presentation_id = args.presentation_url.split('/')[-2]
        except AttributeError:
            log.error("Set --presentation-url to point to a valid Google slide location")
            exit()
        # Create a new Google slide
        page_id = str(uuid.uuid4())
        self.snippets.create_slide(presentation_id, page_id)
        
        meta = reads.read_scan_info(args)
        # print(meta)

        # title
        full_file_name = meta[self.full_file_name][0]
        # self.snippets.create_textbox_with_text(presentation_id, page_id, file_name, 50, 400, 0, 0, 18)  # magnitude
        self.snippets.create_textbox_with_text(presentation_id, page_id, os.path.basename(
            full_file_name)[:-3], 50, 400, 0, 0, 18)  # magnitude
        dims          = meta['exchange_data'][0].replace("(", "").replace(")", "").split(',')
        width         = dims[2]
        height        = dims[1]

        # publish labels and scan info in the new slide
        descr =  f"Particle description: {meta[self.description_1][0]} {meta[self.description_2][0]} {meta[self.description_3][0]}\n"
        descr += f"Scan date: {meta[self.date][0]}\n"
        descr += f"Scan energy: {meta[self.energy][0]} {meta[self.energy][1]}\n"
        descr += f"Pixel size: {meta[self.pixel_size][0]:.02f} {meta[self.pixel_size][1]}\n"
        descr += f"Lens magnification: {meta[self.magnification][0]}\n"
        descr += f"Resolution: {meta[self.resolution][0]:.02f} {meta[self.resolution][1]}\n"
        descr += f"Exposure time: {meta[self.exposure_time][0]:.02f} {meta[self.exposure_time][1]}\n"
        descr += f"Angle step: {meta[self.angle_step][0]:.03f} {meta[self.angle_step][1]}\n"
        descr += f"Number of angles: {meta[self.num_angle][0]}\n"
        descr += f"Projection size: {width} x {height}"
        self.snippets.create_textbox_with_bullets(
            presentation_id, page_id, descr, 240, 200, 0, 27, 8)

        # publish projection label(s)
        self.snippets.create_textbox_with_text(
            presentation_id, page_id, 'Nano-CT projection', 30, 100, 60, 255, 8)
        self.snippets.create_textbox_with_text(
            presentation_id, page_id, 'Micro-CT projection', 30, 100, 60, 375, 8)
                # publish projections

        # publish projection(s)
        proj = reads.read_raw(args)
        # print(proj)   
        if(args.beamline == '32-id'):
            # 32-id datasets include both micro and nano CT data
            for i in range(len(proj)):
                fname = FILE_NAME_PROJ+str(i)+'.jpg'
                # self.publish_projection(args, meta, fname, proj[i], presentation_id, page_id, 210, 210, 0, 100+i*125)
                self.publish_projection(args, meta, fname, proj[i], presentation_id, page_id, i)
        else:
            print('to be completed for micro CT only')
        # publish reconstruction label
        self.snippets.create_textbox_with_text(
            presentation_id, page_id, 'Reconstruction', 30, 150, 270, 0, 10)
        # publish reconstructions
        recon = reads.read_recon(args, meta)    
        if len(recon) == 3:
            # prepare reconstruction
            plots.plot_recon(args, meta, recon, FILE_NAME_RECON)
            with open(FILE_NAME_RECON, 'rb') as f:
                self.dbx.files_upload(
                    f.read(), '/'+FILE_NAME_RECON, dropbox.files.WriteMode.overwrite)
            recon_url = self.dbx.files_get_temporary_link('/'+FILE_NAME_RECON).link            
            self.snippets.create_image(
                presentation_id, page_id, recon_url, 370, 370, 130, 30)

        # publish other labels
        self.snippets.create_textbox_with_text(
            presentation_id, page_id, 'Other info/screenshots', 30, 230, 480, 0, 10)

    def publish_projection(self, args, meta, fname, proj, presentation_id, page_id, i):
        plots.plot_projection(args, meta, proj, fname, i)
        with open(fname, 'rb') as f:
            self.dbx.files_upload(
                f.read(), '/'+fname, dropbox.files.WriteMode.overwrite)
            proj_url = self.dbx.files_get_temporary_link('/'+fname).link            
            self.snippets.create_image(
                presentation_id, page_id, proj_url, 210, 210, 0, 100+i*125)

