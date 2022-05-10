import os
import json
import uuid
import pathlib
import meta
import h5py
import numpy as np
import matplotlib.pyplot as plt
from matplotlib_scalebar.scalebar import ScaleBar
from mpl_toolkits.axes_grid1 import make_axes_locatable

from tomolog_cli import utils
from tomolog_cli import log
from tomolog_cli import TomoLog

__author__ = "Viktor Nikitin,  Francesco De Carlo"
__copyright__ = "Copyright (c) 2022, UChicago Argonne, LLC."
__docformat__ = 'restructuredtext en'
__all__ = ['TomoLog2BM', ]

FILE_NAME_PROJ1 = 'projection_google1.jpg'


class TomoLog2BM(TomoLog):
    '''
    Class to publish experiment meta data, tomography projection and reconstruction on a 
    google slide document.
    '''

    def __init__(self, args):
        super().__init__(args)
        self.sample_in_x_key = '/process/acquisition/flat_fields/sample/in_x'
        # self.binning_key = '/measurement/instrument/detector/binning_x'
        # self.width_key = '/measurement/instrument/detector/roi/size_x'
        # self.height_key = '/measurement/instrument/detector/roi/size_y'

        self.binning_rec = -1
        self.mct_resolution = -1
        self.double_fov = False
        self.file_name_proj1 = FILE_NAME_PROJ1

    def run_log(self):
        # read meta, calculate resolutions
        _, self.meta = meta.read_hdf(self.args.file_name, add_shape=True)
        if (self.meta[self.sample_in_x_key][0] != 0):
            self.double_fov = True
            log.warning('Sample in x is off center: %s. Handling the data set as a double FOV' %
                        self.meta[self.sample_in_x_key][0])
        self.mct_resolution = float(self.meta[self.resolution_key][0])


        presentation_id, page_id = self.init_slide()
        self.publish_descr(presentation_id, page_id)
        proj = self.read_raw()
        recon = self.read_recon()
        self.publish_proj(presentation_id, page_id, proj)
        self.publish_recon(presentation_id, page_id, recon)

    def read_raw(self):
        proj = []
        with h5py.File(self.args.file_name) as fid:
            if self.double_fov == True:
                log.warning('Data read: Handling the data set as a double FOV')
                image_0 = np.flip(fid['exchange/data'][0][:], axis=1)
                image_1 = fid['exchange/data'][-1][:]
                data = np.hstack((image_0, image_1))
            else:
                data = fid['exchange/data'][0][:]
            proj.append(data)
            log.info('Reading CT projection')
            try:
                proj.append(fid['exchange/web_camera_frame'][:])
                log.info('Reading camera frame')
            except:
                pass
        return proj

    def read_recon(self):

        width = int(self.meta[self.width_key][0])
        height = int(self.meta[self.height_key][0])
        binning = int(self.meta[self.binning_key][0])
        recon = []
        coeff_rec = 1

        try:
            basename = os.path.basename(self.args.file_name)[:-3]
            dirname = os.path.dirname(self.args.file_name)
            # set the correct prefix to find the reconstructions
            rec_prefix = 'recon'

            top = os.path.join(dirname+'_rec', basename+'_rec')
            tiff_file_list = sorted(
                list(filter(lambda x: x.endswith(('.tif', '.tiff')), os.listdir(top))))
            z_start = int(tiff_file_list[0].split('.')[0].split('_')[1])
            z_end = int(tiff_file_list[-1].split('.')[0].split('_')[1]) + 1
            height = z_end-z_start
            fname_tmp = os.path.join(top, tiff_file_list[0])
            # take size
            tmp = utils.read_tiff(fname_tmp).copy()

            if self.double_fov == True:
                width = width * 2
                binning_rec = 1
            else:
                binning_rec = width//tmp.shape[0]

            w = width//binning_rec
            h = height
            if self.args.idz == -1:
                self.args.idz = int(h//2)
            if self.args.idy == -1:
                self.args.idy = int(w//2)
            if self.args.idx == -1:
                self.args.idx = int(w//2)

            z = utils.read_tiff(
                f'{dirname}_rec/{basename}_rec/{rec_prefix}_{self.args.idz:05}.tiff').copy()

            # read x,y slices by lines
            y = np.zeros((h, w), dtype='float32')
            x = np.zeros((h, w), dtype='float32')

            for j in range(z_start, z_end):
                zz = utils.read_tiff(
                    f'{dirname}_rec/{basename}_rec/{rec_prefix}_{j:05}.tiff')
                y[j-z_start, :] = zz[self.args.idy]
                x[j-z_start, :] = zz[:, self.args.idx]

            recon = [coeff_rec*x, coeff_rec*y, coeff_rec*z]

            self.binning_rec = binning_rec

            log.info('Adding reconstruction')
        except ZeroDivisionError:
            log.error(
                'Reconstructions for %s are larger than raw data image width. This is the case in a 0-360. Please use: --double-fov' % top)
            log.warning('Skipping reconstruction')
        except:
            log.warning('Skipping reconstruction')

        return recon

    def read_rec_line(self):
        line = None
        try:
            basename = os.path.basename(self.args.file_name)[:-3]
            dirname = os.path.dirname(self.args.file_name)
            with open(f'{dirname}_rec/{basename}_rec/rec_line.txt', 'r') as fid:
                line = fid.readlines()[0]
        except:
            log.warning('Skipping the command line for reconstruction')
            line = ''
        return line

    def publish_proj(self, presentation_id, page_id, proj):
        # 32-id datasets may include both nanoCT and microCT data as proj[0] and proj[1] respectively
        log.info('Micro Tomography Instrument')
        log.info('Plotting microCT projection')
        self.plot_projection(proj[0], self.file_name_proj0)
        proj_url = self.dbx.upload(self.file_name_proj0)
        self.google.create_image(
            presentation_id, page_id, proj_url, 170, 170, 0, 145)

        self.google.create_textbox_with_text(
            presentation_id, page_id, 'Micro-CT projection', 90, 20, 50, 150, 8, 0)
        try:
            log.info('Plotting frame the IP camera')
            self.plot_projection(proj[1], self.file_name_proj1)
            proj_url = self.dbx.upload(self.file_name_proj1)
            self.google.create_image(
                presentation_id, page_id, proj_url, 170, 170, 0, 270)

            self.google.create_textbox_with_text(
                presentation_id, page_id, 'Frame from the IP camera in the hutch', 160, 20, 10, 290, 8, 0)
        except:
            log.warning('No frame from the IP camera')

    def publish_recon(self, presentation_id, page_id, recon):
        if len(recon) == 3:
            # publish reconstructions
            self.plot_recon(recon, self.file_name_recon)
            recon_url = self.dbx.upload(self.file_name_recon)
            rec_line = self.read_rec_line()
            self.google.create_image(
                presentation_id, page_id, recon_url, 370, 370, 130, 25)
            self.google.create_textbox_with_text(
                presentation_id, page_id, 'Reconstruction', 90, 20, 270, 0, 10, 0)
            self.google.create_textbox_with_text(
                presentation_id, page_id, rec_line, 1000, 20, 185, 391, 6, 0)

    def plot_projection(self, proj, fname):

        # auto-adjust colorbar values according to a histogram
        mmin, mmax = utils.find_min_max(proj)
        proj[proj > mmax] = mmax
        proj[proj < mmin] = mmin

        # plot
        fig = plt.figure(constrained_layout=True, figsize=(6, 4))
        ax = fig.add_subplot()
        im = ax.imshow(proj, cmap='gray')
        # Create scale bar
        scalebar = ScaleBar(self.mct_resolution, "um", length_fraction=0.25)
        ax.add_artist(scalebar)
        divider = make_axes_locatable(ax)
        cax = divider.append_axes("right", size="5%", pad=0.1)
        plt.colorbar(im, cax=cax)
        # plt.show()
        # save
        plt.savefig(fname, bbox_inches='tight', pad_inches=0, dpi=300)
        plt.cla()
        plt.close(fig)

    def plot_recon(self, recon, fname):
        fig = plt.figure(constrained_layout=True, figsize=(6, 12))
        grid = fig.add_gridspec(3, 1, height_ratios=[1, 1, 1])
        slices = ['x', 'y', 'z']
        # autoadjust colorbar values according to a histogram

        if self.args.min == self.args.max:
            self.args.min, self.args.max = utils.find_min_max(
                np.concatenate(recon))

        sl = [self.args.idx, self.args.idy, self.args.idz]
        for k in range(3):
            recon[k][0, 0] = self.args.max
            recon[k][0, 1] = self.args.min
            recon[k][recon[k] > self.args.max] = self.args.max
            recon[k][recon[k] < self.args.min] = self.args.min
            ax = fig.add_subplot(grid[k])
            im = ax.imshow(recon[k], cmap='gray')
            # Create scale bar
            scalebar = ScaleBar(self.mct_resolution *
                                self.binning_rec, "um", length_fraction=0.25)
            ax.add_artist(scalebar)
            divider = make_axes_locatable(ax)
            cax = divider.append_axes("right", size="5%", pad=0.1)
            plt.colorbar(im, cax=cax)
            ax.set_ylabel(f'slice {slices[k]}={sl[k]}', fontsize=14)
        # save
        plt.savefig(fname, bbox_inches='tight', pad_inches=0, dpi=300)
        plt.cla()
        plt.close(fig)