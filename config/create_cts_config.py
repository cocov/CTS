import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import RegularPolygon
from matplotlib.collections import PatchCollection
from cts_core.camera import Camera


class LED(object):
    def __init__(self, id, x, y, angle=0,
                 radius_hex=12.15, board=None, sector=None):
        self.id = id
        self.x = x
        self.y = y
        self.angle = angle
        self.radius_hex = radius_hex
        self.board = board
        self.sector = sector

    def get_polygon(self):
        return RegularPolygon(
            (self.x, self.y),
            6,
            radius=self.radius_hex * 2 / np.sqrt(3) - 0.05,
            orientation=np.pi / 6 + self.angle
        )


class CTS_board(object):
    def __init__(self, id, x, y, angle=0, sector=None):
        x_leds = np.array([
            -17.53, -38.59, -38.59, 24.56, 3.50, 3.50, 66.64, 45.59,
            45.59, 108.73, 87.69, 87.69, -38.59, -59.62, -59.62, 3.50,
            -17.53, -17.53, 45.59, 24.56, 24.56, 87.69, 66.64, 66.64,
            -59.62, -80.68, -80.68, -17.53, -38.59, -38.59, 24.56, 3.50,
            3.50, 66.64, 45.59, 45.59, -80.68, -101.72, -101.72, -38.59,
            -59.62, -59.62, 3.50, -17.53, -17.53, 45.59, 24.56, 24.56
        ]) + 38.59 - 12.15/np.sqrt(3)
        y_leds = np.array([
            54.68, 42.52, 66.82, 54.68, 42.52, 66.82, 54.68, 42.52,
            66.82, 54.68, 42.52, 66.82, 18.22, 6.07, 30.38, 18.22,
            6.07, 30.38, 18.22, 6.07, 30.38, 18.22, 6.07, 30.38,
            -18.23, -30.38, -6.07, -18.23, -30.38, -6.07, -18.23, -30.38,
            -6.07, -18.23, -30.38, -6.07, -54.68, -66.82, -42.53, -54.68,
            -66.82, -42.53, -54.68, -66.82, -42.53, -54.68, -66.82, -42.53
        ]) - 66.82 - 12.15
        id_leds = np.array([1, 2, 0, 4, 5, 3, 7, 8,
                            6, 10, 11, 9, 13, 14, 12, 16,
                            17, 15, 19, 20, 18, 22, 23, 21,
                            25, 26, 24, 28, 29, 27, 31, 32,
                            30, 34, 35, 33, 37, 38, 36, 40,
                            41, 39, 43, 44, 42, 46, 47, 45])
        coord_leds = np.vstack((x_leds, y_leds)).transpose()
        rot_matrix = np.array(
            [[np.cos(angle), np.sin(angle)], [- np.sin(angle), np.cos(angle)]]
        )
        coord_leds_rot = np.dot(coord_leds, rot_matrix)
        self.id = id
        self.x = x
        self.y = y
        self.angle = angle
        self.leds = []
        for i in range(48):
            self.leds.append(
                LED(
                    id_leds[i],
                    coord_leds_rot[i, 0] + x,
                    coord_leds_rot[i, 1] + y,
                    angle=angle, board=id, sector=sector
                )
            )

    def plot(self, axis=None):
        polys = []
        for led in self.leds:
            polys.append(led.get_polygon())
        hex_collection = PatchCollection(polys)
        if axis is None:
            axis = plt.subplot(111)
        axis.add_collection(hex_collection)

    def overlay_boards_id(self):
        board_leds_pos = np.array([[l.x, l.y] for l in self.leds])
        board_mean_pos = np.mean(board_leds_pos, axis=0)
        return plt.text(
            board_mean_pos[0],
            board_mean_pos[1],
            self.id,
            fontsize=12,
            horizontalalignment='center',
            verticalalignment='center'
        )


class CTS_sector(object):
    def __init__(self, id, board_ids, angle=0):
        """
        A CTS_sector contains 12 boards
        :param board_ids: array of 12 ints containing the board id from the
        center and then going to the exterior and clockwise (from 1 to 27).
        None indicates a missing card
        :param angle: angle of the sector in radians
        0 deg is a sector like foloowing ascii-art with cta labels upside down,
        the '.' indicates the center of the CTS.
        The order of board_ids corresponding to each board is shown as well:

             ._________
             /  /  /  /
            /_1/_4/_9/
           /  /  /  /
          /_2/_3/_8/
         /  /  /  /
        /_5/_6/_7/

        """
        if len(board_ids) != 9:
            raise ValueError("a sector must be given 9 boards id.")
        board_size_x = 12 * 12.15 * 2 / np.sqrt(3)
        shift_x = 2 * board_size_x / 3 - 4 * 12.15 / np.sqrt(3)
        board_size_y = 12 * 12.15
        # how much to horiz. offset each card in units of horiz. card size
        nboards_size_x = [0, 0, 1, 1, 0, 1, 2, 2, 2]
        # how much to vert. offset each card in units of vert. card size
        nboards_size_y = [0, -1, -1, 0, -2, -2, -2, -1, 0]
        # for each vertical offset an horizontal offset is needed
        nshifts_x = nboards_size_y
        self.id = id
        self.boards = []
        for i in range(9):
            if board_ids is None:
                continue
            dx = nboards_size_x[i] * board_size_x + nshifts_x[i] * shift_x
            dy = nboards_size_y[i] * board_size_y
            dx_rot = dx * np.cos(angle) - dy * np.sin(angle)
            dy_rot = dx * np.sin(angle) + dy * np.cos(angle)
            self.boards.append(
                CTS_board(board_ids[i], dx_rot, dy_rot, angle=angle, sector=id)
            )

    def get_leds(self):
        leds = []
        for board in self.boards:
            leds.extend(board.leds)
        return leds

    def plot(self, axis=None):
        polys = []
        for led in self.get_leds():
            polys.append(led.get_polygon())
        hex_collection = PatchCollection(polys)
        if axis is None:
            axis = plt.subplot(111)
        axis.add_collection(hex_collection)

    def overlay_boards_id(self):
        texts = []
        for board in self.boards:
            texts.append(board.overlay_boards_id())
        return texts


class CTS:
    def __init__(self, board_ids, angle=0):
        """

        :param board_ids: a 3 by 9 array (1 line per sector, 1 colum per
        board_id in the order defined in CTS_sector), a list of 3 lists
        or a tupe of 3 tuples.
        :param angle: angle of rotation of the CTS in degrees
        """
        board_ids = np.array(board_ids)
        if board_ids.shape != (3, 9):
            raise ValueError(
                "board_ids must be either:"
                "a 3 by 9 array (1 line per sector, 1 colum per board_id"
                "in the order defined in CTS_sector), a list of 3 lists or"
                "a tupe of 3 tuples."
            )
        self.sectors = []
        self.angle = angle
        for i in range(3):
            self.sectors.append(CTS_sector(
                id=i,
                board_ids=board_ids[i, :],
                angle=angle/180*np.pi + i*-2*np.pi/3 + np.pi/6
            ))

    def get_leds(self):
        leds = []
        for sector in self.sectors:
            leds.extend(sector.get_leds())
        return leds

    def create_config(self):
        camera = Camera('camera_config.cfg')
        file_cfg = open('cts_config_%d.cfg' % self.angle, "w+")
        pixels_xy = np.array([pixel.center for pixel in camera.Pixels])
        print('# HEADER', file=file_cfg)
        print(
            '# led_type', 'led_number', 'led_patch', 'led_board',
            'led_id_in_board', 'led_id_in_patch', 'x[mm]', 'y[mm]',
            'pixel_sw', 'patch_sw', sep='\t', file=file_cfg
        )
        print('# DATA', file=file_cfg)
        leds = self.get_leds()
        for i, led in enumerate(leds):
            closest_px = np.argmin(
                np.linalg.norm(pixels_xy - np.array([led.x, led.y]), axis=1)
            )
            dist_pixel_led = np.linalg.norm(
                pixels_xy[closest_px, :] - np.array([led.x, led.y])
            )
            assert dist_pixel_led < 0.1  # make sure offset is small
            led_patch = int(np.floor(i % 48 / 3)) + (led.board - 1) * 16
            led_id_in_patch = i % 3
            print('AC', i, led_patch, led.board - 1, led.id, led_id_in_patch,
                  '{0:.2f}'.format(led.x), '{0:.2f}'.format(led.y),
                  closest_px, camera.Pixels[closest_px].patch,
                  sep='\t', file=file_cfg)
        nled_ac = i + 1
        for i in range(nled_ac):
            led = leds[i]
            closest_px = np.argmin(
                np.linalg.norm(pixels_xy - np.array([led.x, led.y]), axis=1)
            )
            dist_pixel_led = np.linalg.norm(
                pixels_xy[closest_px, :] - np.array([led.x, led.y])
            )
            assert dist_pixel_led < 0.1  # make sure offset is small
            led_patch = int(np.floor(i % 48 / 3)) + (led.board - 1) * 16
            led_id_in_patch = i % 3
            print('DC', i + nled_ac, led_patch, led.board - 1, led.id,
                  led_id_in_patch, '{0:.2f}'.format(led.x),
                  '{0:.2f}'.format(led.y),
                  closest_px, camera.Pixels[closest_px].patch,
                  sep='\t', file=file_cfg)
        print(file_cfg.name, 'created')

    def plot(self, axis=None):
        polys = []
        for led in self.get_leds():
            polys.append(led.get_polygon())
        hex_collection = PatchCollection(polys)
        if axis is None:
            axis = plt.subplot(111)
        axis.add_collection(hex_collection)

    def overlay_boards_id(self):
        texts = []
        for sector in self.sectors:
            texts.extend(sector.overlay_boards_id())
        return texts


if __name__ == '__main__':
    cts0 = CTS(
        [
            [3, 17, 16, 15, 27, 26, 25, 24, 23],
            [1, 6, 5, 4, 11, 10, 9, 8, 7],
            [2, 14, 13, 12, 22, 21, 20, 19, 18]
        ], angle=0)
    cts0.create_config()
    cts120 = CTS(
        [
            [3, 17, 16, 15, 27, 26, 25, 24, 23],
            [1, 6, 5, 4, 11, 10, 9, 8, 7],
            [2, 14, 13, 12, 22, 21, 20, 19, 18]
        ], angle=120)
    cts120.create_config()
    cts240 = CTS(
        [
            [3, 17, 16, 15, 27, 26, 25, 24, 23],
            [1, 6, 5, 4, 11, 10, 9, 8, 7],
            [2, 14, 13, 12, 22, 21, 20, 19, 18]
        ], angle=240)
    cts240.create_config()
    cts0.plot()
    cts0.overlay_boards_id()
    plt.axis('equal')
    plt.grid(True)
    plt.show()
