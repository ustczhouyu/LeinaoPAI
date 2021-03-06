#coding:utf-8

import os
import re
import time
import keras
from keras.backend.tensorflow_backend import set_session
import numpy as np
import sys
import requests
import json
import logging
logger = logging.getLogger("user_activity")

from Validation_BasicFunction import mode, Test_Set, readYUVFile, calculatePSNR 
import tensorflow

# 限制tensorflow的GPU显存使用，不执行的话，所有显存被占用，无法执行其它模型！
config = tensorflow.ConfigProto()
config.gpu_options.per_process_gpu_memory_fraction = 0.2
set_session(tensorflow.Session(config=config))


# 进行tensor模型的深度学习
def net_forward(model: keras.engine.training.Model, image, patch_size):

    # 存储图像的像素信息
    res = image.copy()

    # 每隔patch_size对图像进行分割计算    
    for sy in range(0, image.shape[0], patch_size):
        for sx in range(0, image.shape[1], patch_size):
            
            # 区块的另一端坐标。（sy，sx）为一端坐标
            ey = min(image.shape[0], sy+patch_size)
            ex = min(image.shape[1], sx+patch_size)

            # 对像素值进行归一化
            patch = image[sy:ey, sx:ex] / 255.0

            # 深度学习运行（前向网络）
            output = model.predict(patch.reshape(1, patch.shape[0], patch.shape[1], 1))
            output *= 255.0

            # 转为无符号整数（0 到 255）
            res_patch = np.uint8(np.clip(np.round_(output.reshape(patch.shape[0], patch.shape[1])), 0, 255))
            res[sy:ey, sx:ex] = res_patch
    return res


# 对图片进行评分，程序入口，首先设计设备和显存占用	
def keras_validation(kerasModels, patchSize):

    # 使用GPU-2
    with tensorflow.device('/gpu:2'):

        # 开始评分
        acc, cost = keras_validation_core(kerasModels, patchSize)

    return acc, cost
    


# 对图片进行评分的核心程序	
def keras_validation_core(kerasModels, patchSize):
    
    psnr_accu = 0.0
    counter = 0
    t = time.time()

    qp_list = [38, 45, 52]

    for ii in range(3):

        # 参数
        qp = qp_list[ii]

        # keras模型文件的路径
        kerasModels_path = kerasModels[ii]

        # karas模型
        model = keras.models.load_model(kerasModels_path, compile=False)
        
        for f in os.listdir('./%s/%s_Q%d_yuv' % (Test_Set, mode, qp)):

            # 获取图片的序号、宽、高
            tmpl = re.split('\_|x|\.', f)
            i = int(tmpl[0])
            w = int(tmpl[1])
            h = int(tmpl[2])

            # 读取测试集的YUV文件
            (Yo, Uo, Vo) = readYUVFile('./%s/%s_yuv/%d.yuv' % (Test_Set, mode, i), w, h)
            (Yd, Ud, Vd) = readYUVFile('./%s/%s_Q%d_yuv/%s' % (Test_Set, mode, qp, f), w, h)

            # 在3个参数下对图像进行深度学习
            Yr = net_forward(model, Yd, patchSize)
            Ur = net_forward(model, Ud, patchSize)
            Vr = net_forward(model, Vd, patchSize)

            # 计算PSNR
            a_psnr_y = calculatePSNR(Yo, Yr)
            a_psnr_u = calculatePSNR(Uo, Ur)
            a_psnr_v = calculatePSNR(Vo, Vr)
            psnr_aft = (6.0 * a_psnr_y + a_psnr_u + a_psnr_v) / 8.0
            psnr_accu += psnr_aft

            # 计数
            counter += 1
            print ('counter = %3d : psnr_aft = %f , total cost time = %f' % (counter, psnr_aft, time.time()-t))
            
    return psnr_accu / counter, time.time() - t


