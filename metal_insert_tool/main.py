import os
import sys
import dicom
from glob import glob 
import numpy as np
import scipy.ndimage
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas


class Non_MA:
    def __init__(self):
        self.old_path = None
    
    def set_img(self, path):
        if path != self.old_path:
            self.origin_non_MA = dicom.read_file(path).pixel_array.astype(float)
            self.old_path = path

    def insert_metal(self, metal, y, x, metal_r=None, y2=None, x2=None):        
        m_y, m_x = metal.shape
        inserted_metal = self.origin_non_MA.copy()
        inserted_metal[y:y + m_y, x:x + m_x] += metal

        if metal_r is not None:
            m_y, m_x = metal_r.shape
            inserted_metal[y2:y2 + m_y, x2:x2 + m_x] += metal_r
        
        return inserted_metal.clip(np.amin(inserted_metal), 4095)


class MA:
    def _trim(x):
        return x if x >= 4090 else 0
    metal_extract = np.vectorize(_trim)
    
    def __init__(self):
        self.old_path = None
        self.metal_cnt = 1

    def _get_metal_range(self, metal_img):
        metal_range = np.where(metal_img != 0)
        y_min, y_max = min(metal_range[0]), max(metal_range[0])
        x_min, x_max = min(metal_range[1]), max(metal_range[1])
        return metal_img[y_min:y_max, x_min:x_max]

    def set_img(self, path):
        if path != self.old_path:
            self.old_path = path
            self.origin_MA = dicom.read_file(path).pixel_array.astype(float)
            flaged_MA = (self.origin_MA >= 4090).astype(int)

            flaged_MA_X = flaged_MA.shape[1]
            left_MA, right_MA = flaged_MA[:, 0:flaged_MA_X//2], flaged_MA[:, flaged_MA_X//2:flaged_MA_X]

            cliped_MA = self.origin_MA * flaged_MA
            if sum(sum(left_MA)) > 0 or sum(sum(right_MA)) > 0:
                self.metal_cnt = 2
                self._metal = self._get_metal_range(cliped_MA[:, 0:cliped_MA//2]) 
                self._metal_r = self._get_metal_range(cliped_MA[:, cliped_MA//2: cliped_MA]) 
            else:               
                self.metal_cnt = 1
                self._metal = self._get_metal_range(cliped_MA)
    
    def _get_metal(self, metal, zoom, angle):
        if angle > 0:
            metal = scipy.ndimage.rotate(metal, angle)
        if zoom != 1:
            metal = scipy.ndimage.zoom(metal, zoom, order=0)
        return metal

    def get_metal(self, zoom=1, angle=0, zoom2=1, angle2=0):       
        if self.metal_cnt == 1:
            return self._get_metal(self._metal, zoom, angle)
        else:
            return self._get_metal(self._metal, zoom, angle), self._get_metal(self._metal_r, zoom2, angle2)


class MyWindow(QWidget):
    def __init__(self):
        super().__init__()

        if os.path.exists(os.getcwd() + "\\inserted") is False:
            os.mkdir(os.getcwd() + "\\inserted")

        self.data_path = os.getcwd() + "\\inserted\\"
        files = [os.path.basename(x)[:-4].split("_") for x in glob(self.data_path + "*")]
        self.file_dict = {int(f[0] + f[1]) : {int(f[2] + f[3]) : int(f[4])} for f in files}
        
        self._inserted_metal = None
        self.non_MA = Non_MA()
        self.metal = MA()
        
        self.setupUI()

    def setupUI(self):
        self.setGeometry(600, 200, 768, 768)
        self.setWindowTitle("Metal Insertion v0.1")

        self.MA_path = QLineEdit()
        self.non_MA_path = QLineEdit()        
        self.location_edit = QLineEdit()          
        self.zoom_edit = QLineEdit()
        self.angle_edit = QLineEdit()
        
        self.location_edit2 = QLineEdit()          
        self.zoom_edit2 = QLineEdit()
        self.angle_edit2 = QLineEdit()

        self.pushButton = QPushButton("Set Image")  
        self.pushButton.clicked.connect(self.input_imgs)
        self.saveButton = QPushButton("Save Image")
        self.saveButton.clicked.connect(self.save_img)

        self.fig = plt.Figure()
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvas(self.fig)

        upLayout = QVBoxLayout()
        upLayout.addWidget(self.canvas)
        
        downLayout = QVBoxLayout()
        downLayout.addWidget(QLabel("MA Path: "))
        downLayout.addWidget(self.MA_path)
        downLayout.addWidget(QLabel("NON MA Path: "))
        downLayout.addWidget(self.non_MA_path)
        downLayout1 = QHBoxLayout()
        downLayout1.addWidget(QLabel("Y X(0 ~ 512) : "))
        downLayout1.addWidget(self.location_edit)
        downLayout1.addWidget(QLabel("Zoom(real number): "))
        downLayout1.addWidget(self.zoom_edit)
        downLayout1.addWidget(QLabel("angle(0 ~ 360) : "))
        downLayout1.addWidget(self.angle_edit)
        downLayout1.addWidget(self.pushButton)
        downLayout1.addWidget(self.saveButton)
        downLayout2 = QHBoxLayout()
        downLayout2.addWidget(QLabel("Y X(0 ~ 512) : "))
        downLayout2.addWidget(self.location_edit2)
        downLayout2.addWidget(QLabel("Zoom(real number): "))
        downLayout2.addWidget(self.zoom_edit2)
        downLayout2.addWidget(QLabel("angle(0 ~ 360) : "))
        downLayout2.addWidget(self.angle_edit2)
        downLayout.addStretch(1)

        layout = QVBoxLayout()        
        layout.addLayout(upLayout)
        layout.addLayout(downLayout)
        layout.addLayout(downLayout1)
        layout.addLayout(downLayout2)
        layout.setStretchFactor(upLayout, 1)
        layout.setStretchFactor(downLayout, 0)

        self.setLayout(layout)

    def _get_path(self):
        non_MA_path = self.non_MA_path.text()
        MA_path = self.MA_path.text()        
        print("Params non MA : ", non_MA_path)
        print("Params_____MA : ", MA_path)
        return non_MA_path, MA_path

    def _get_input_params(self):
        locate = (0, 0) if len(self.location_edit.text()) == 0 else [int(i) for i in self.location_edit.text().split()]
        zoom = 1.0 if len(self.zoom_edit.text()) == 0 else float(self.zoom_edit.text())
        angle = 0 if len(self.angle_edit.text()) == 0 else int(self.angle_edit.text())
        print("Params_______ : ", locate, zoom, angle)
        return locate, zoom, angle

    def _get_input_params2(self):
        locate2 = (0, 0) if len(self.location_edit.text()) == 0 else [int(i) for i in self.location_edit2.text().split()]
        zoom2 = 1.0 if len(self.zoom_edit.text()) == 0 else float(self.zoom_edit2.text())
        angle2 = 0 if len(self.angle_edit.text()) == 0 else int(self.angle_edit2.text())
        print("Params_______ : ", locate2, zoom2, angle2)
        return locate2, zoom2, angle2
        
    def input_imgs(self):
        non_MA_path, MA_path = self._get_path()
        """
        For Test
        MA_path = r"C:\DW_Intern\DCM\01_MA_Image\15369989\15369989_0070.DCM"
        non_MA_path = r"C:\DW_Intern\DCM\03_Non_MA\15858650\15858650_0000.DCM"
        """
        if self.non_MA is None or self.MA_path is None:
            return
        
        self.non_MA.set_img(non_MA_path)
        self.metal.set_img(MA_path)

        l, z, a = self._get_input_params()
        if self.metal.metal_cnt == 1:
            metal = self.metal.get_metal(z, a)
            self._inserted_metal = self.non_MA.insert_metal(metal, l[0], l[1])
        else:
            l2, z2, a2 = self._get_input_params2()
            metal, metal2 = self.metal.get_metal(z, a, z2, a2)
            self._inserted_metal = self.non_MA.insert_metal(metal, l[0], l[1], metal2, l2[0], l2[1])

        self.ax.imshow(self._inserted_metal, cmap='gray')
        self.canvas.draw()

    def save_img(self):
        non_ma_num = self.non_MA_path.text().split("\\")[-1][:-4].split("_")
        ma_num = self.MA_path.text().split("\\")[-1][:-4].split("_")

        self.file_dict[int(sum(non_ma_num))][int(sum(ma_num))] += 1
        path_cnt = self.file_dict[int(sum(non_ma_num))][int(sum(ma_num))]
        path = "%s\\inserted\\%s_%s_%s_%s_%d"%(os.getcwd(), *non_ma_num, *ma_num, path_cnt)
        print(path)
        print("Save Img : ", path)
        np.save(path+".npy", self._inserted_metal)
        self.fig.savefig(path+".png")
        

if __name__ == "__main__":    
    app = QApplication(sys.argv)
    window = MyWindow()
    window.show()
    app.exec_()