# -*- coding:utf-8 -*-
# @author: ShuleHao
# @contact: 2571540718@qq.com
# @Blog:https://blog.csdn.net/hubuhgyf?type=blog
"""
    文件说明：svm层的模型文件
"""
from .rom import generate_gort_weights
import torch
from torch import nn
import torch.nn.functional as F
from torch import autograd
import numpy as np


def pad_data(x, d1, n):
    pad = lambda xz: F.pad(xz, ((0, d1-n), (0, 0)), mode='constant',
                           value=0)
    return pad(x)


def approximate_arccos_features(x, M):
    nsamples = M.size(0)
    n = x.size(1)
    d1 = M.size(1)
    if d1 > n:
        x = pad_data(x, d1, n)
    Mx = F.relu(x.matmul(M.t()))
    K = Mx * np.sqrt(2.0 / nsamples)
    return K


def approximate_rbf_features(x, M, **kwargs):
    '''
   来自内核参数
    '''
    nsamples = M.size(0)
    n = x.size(1) # input dimension
    d1 = M.size(1)
    if d1 > n:
        x = pad_data(x, d1, n)

    if 'gamma' in kwargs and kwargs['gamma'] is not None:
        gamma = kwargs['gamma']
    else:
        gamma = 1. / n

    sigma = 1.0 / np.sqrt(2 * gamma)
    def get_rbf_fourier_features(M, x):
        features = x.matmul(M.t()) / sigma
        features = torch.cat((torch.cos(features),
                              torch.sin(features)), dim=1)
        return features

    Mx = get_rbf_fourier_features(M, x) / np.sqrt(nsamples)
    return Mx


class KernelLayer(nn.Module):
    """
   这是一个近似于内核诱导的特征图的层。目前它支持 RBF 内核（具有正交随机特征）和 Arccos 内核
    """
    def __init__(self, in_features, out_features, kernel_type=None, gamma=None):
        super(KernelLayer, self).__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.gamma = gamma

        if kernel_type is None:
            self.kernel_type = 'rbf'
        else:
            if not kernel_type.lower() in ['rbf', 'arccos']:
                raise ValueError('Unknown kernel type!')

            self.kernel_type = kernel_type

        if self.kernel_type == 'rbf':
            k = out_features / (4 * (in_features + 1))
        else:
            k = out_features / (2 * (in_features + 1))

        W, _ = generate_gort_weights(k, in_features)

        self.weight = autograd.Variable(torch.from_numpy(W).type(torch.FloatTensor))
        if self.kernel_type.lower() == 'rbf':
            self.kernel_features = lambda x: approximate_rbf_features(x, self.weight, gamma=self.gamma)
        else:
            self.kernel_features = lambda x: approximate_arccos_features(x, self.weight)


    def forward(self, x):
        return self.kernel_features(x)

    def _apply(self, fn):
        super(KernelLayer, self)._apply(fn)
        if self.weight is not None:
            # Variables stored in modules are graph leaves, and we don't
            # want to create copy nodes, so we have to unpack the data.
            self.weight.data = fn(self.weight.data)
            if self.weight._grad is not None:
                self.weight._grad.data = fn(self.weight._grad.data)



