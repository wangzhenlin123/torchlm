import os
import cv2
import math
import torch
import random
import numpy as np
from pathlib import Path

import torchvision.transforms
from torch import Tensor
from abc import ABCMeta, abstractmethod
from typing import Tuple, Union, List, Optional, Callable
from . import functional as F

# base element_type
Base_Element_Type = Union[np.ndarray, Tensor]
Image_InOutput_Type = Base_Element_Type  # image
Landmarks_InOutput_Type = Base_Element_Type  # landmarks

__all__ = [
    "LandmarksCompose",
    "LandmarksNormalize",
    "LandmarksUnNormalize",
    "LandmarksToTensor",
    "LandmarksToNumpy",
    "LandmarksResize",
    "LandmarksClip",
    "LandmarksAlign",
    "LandmarksRandomCenterCrop",
    "LandmarksRandomHorizontalFlip",
    "LandmarksHorizontalFlip",
    "LandmarksRandomScale",
    "LandmarksRandomTranslate",
    "LandmarksRandomRotate",
    "LandmarksRandomShear",
    "LandmarksRandomHSV",
    "LandmarksRandomMask",
    "LandmarksRandomBlur",
    "LandmarksRandomBrightness",
    "LandmarksRandomPatches",
    "LandmarksRandomPatchesWithAlpha",
    "LandmarksRandomBackgroundWithAlpha",
    "BindAlbumentationsTransform",
    "BindTorchVisionTransform",
    "bind"
]


def autodtye_array(
        call_array_func: Callable
) -> Callable:
    # A Pythonic style to auto convert input & output dtype.
    def wrapper(
            self,
            img: Image_InOutput_Type,
            landmarks: Landmarks_InOutput_Type
    ) -> Tuple[Image_InOutput_Type, Landmarks_InOutput_Type]:
        # Type checks
        assert all(
            [isinstance(_, (np.ndarray, Tensor))
             for _ in (img, landmarks)]
        ), "Error dtype, must be np.ndarray or Tensor!"

        if any((
                isinstance(img, Tensor),
                isinstance(landmarks, Tensor)
        )):
            img = F.to_numpy(img)
            landmarks = F.to_numpy(landmarks)
            img, landmarks = call_array_func(self, img, landmarks)
            img = F.to_tensor(img)
            landmarks = F.to_tensor(landmarks)
        else:
            img, landmarks = call_array_func(self, img, landmarks)

        return img, landmarks

    return wrapper


def autodtye_tensor(
        call_tensor_func: Callable
) -> Callable:
    # A Pythonic style to auto convert input & output dtype.
    def wrapper(
            self,
            img: Image_InOutput_Type,
            landmarks: Landmarks_InOutput_Type
    ) -> Tuple[Image_InOutput_Type, Landmarks_InOutput_Type]:
        # Type checks
        assert all(
            [isinstance(_, (np.ndarray, Tensor))
             for _ in (img, landmarks)]
        ), "Error dtype, must be np.ndarray or Tensor!"

        if any((
                isinstance(img, np.ndarray),
                isinstance(landmarks, np.ndarray)
        )):
            img = F.to_tensor(img)
            landmarks = F.to_tensor(landmarks)
            img, landmarks = call_tensor_func(self, img, landmarks)
            img = F.to_numpy(img)
            landmarks = F.to_numpy(landmarks)
        else:
            img, landmarks = call_tensor_func(self, img, landmarks)

        return img, landmarks

    return wrapper


class LandmarksTransform(object):
    __metaclass__ = ABCMeta

    def __init__(self):
        # affine records
        self.rotate: float = 0.
        self.scale_x: float = 1.0
        self.scale_y: float = 1.0
        self.trans_x: float = 0.
        self.trans_y: float = 0.
        self.flag: bool = False
        self.is_numpy: bool = True

    @abstractmethod
    def __call__(
            self,
            img: Image_InOutput_Type,
            landmarks: Landmarks_InOutput_Type
    ) -> Tuple[Image_InOutput_Type, Landmarks_InOutput_Type]:
        """
        :param img: np.ndarray | Tensor, H x W x C
        :param landmarks: np.ndarray | Tensor, shape (?, 2), the format is (x1,y1) for each row.
        :return:
        """
        raise NotImplementedError

    def apply_affine_to(
            self,
            other_landmarks: Landmarks_InOutput_Type,
            scale: Optional[bool] = True,
            translate: Optional[bool] = True,
            rotate: Optional[bool] = False,
            **kwargs
    ) -> Landmarks_InOutput_Type:
        _ = kwargs  # un-used
        if translate:
            other_landmarks[:, 0] -= self.trans_x
            other_landmarks[:, 1] -= self.trans_y
        if scale:
            other_landmarks[:, 0] *= self.scale_x
            other_landmarks[:, 1] *= self.scale_y
        if rotate:
            # TODO: add rotation
            pass
        return other_landmarks

    def clear_affine(self):
        self.rotate = 0.
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.trans_x = 0.
        self.trans_y = 0.
        self.flag = False


# Bind TorchVision Transforms
class BindTorchVisionTransform(LandmarksTransform):
    """TODO: add docs"""
    _Supported_Image_Only_Set: Tuple = (
        torchvision.transforms.Normalize,
        torchvision.transforms.ColorJitter,
        torchvision.transforms.Grayscale,
        torchvision.transforms.RandomGrayscale,
        torchvision.transforms.RandomErasing,
        torchvision.transforms.GaussianBlur,
        torchvision.transforms.RandomInvert,
        torchvision.transforms.RandomPosterize,
        torchvision.transforms.RandomSolarize,
        torchvision.transforms.RandomAdjustSharpness,
        torchvision.transforms.RandomAutocontrast,
        torchvision.transforms.RandomEqualize
    )

    def __init__(self, transform: torch.nn.Module):
        super(BindTorchVisionTransform, self).__init__()
        assert isinstance(transform, self._Supported_Image_Only_Set), \
            f"Only supported image only transform, " \
            f"{self._Supported_Image_Only_Set}"

        self.transform_internal = transform

    @autodtye_tensor
    def __call__(
            self,
            img: Image_InOutput_Type,
            landmarks: Landmarks_InOutput_Type
    ) -> Tuple[Image_InOutput_Type, Landmarks_InOutput_Type]:
        # Image only transform from torchvision,
        # just let the landmarks unchanged.
        self.flag = True
        return self.transform_internal(img), landmarks


class BindAlbumentationsTransform(LandmarksTransform):

    # TODO: 需要修改
    def __init__(self, transform: torch.nn.Module):
        super(BindAlbumentationsTransform, self).__init__()
        self.transform_internal = transform

    def __call__(
            self,
            img: Image_InOutput_Type,
            landmarks: Landmarks_InOutput_Type
    ) -> Tuple[Image_InOutput_Type, Landmarks_InOutput_Type]:
        # TODO: update this method to bind ImageOnly|DualTransform
        return super(BindAlbumentationsTransform, self).__call__(
            img,
            landmarks
        )


class BindLambdaTransform(LandmarksTransform):
    """绑定一个自定义函数，ImageOnly或Dual均可"""

    # TODO: 需要修改
    def __init__(self, call_func: Callable):
        super(BindLambdaTransform, self).__init__()
        if not callable(call_func):
            raise TypeError(
                "Argument lambd should be callable, "
                "got {}".format(repr(type(call_func).__name__))
            )
        self.call_func = call_func

    def __call__(
            self,
            img: Image_InOutput_Type,
            landmarks: Landmarks_InOutput_Type
    ) -> Tuple[Image_InOutput_Type, Landmarks_InOutput_Type]:
        # TODO: update this method to bind ImageOnly|DualTransform
        return super(BindLambdaTransform, self).__call__(
            img,
            landmarks
        )


Bind_Transform_Input_Type = Union[
    torch.nn.Module,
    torch.nn.Module  # TODO 修改成Albumentations类型
]

Bind_Transform_Output_Type = Union[
    BindTorchVisionTransform,
    BindAlbumentationsTransform
]


# bind method
def bind(
        transform: Bind_Transform_Input_Type
) -> Bind_Transform_Output_Type:
    # bind torchvision transform
    if isinstance(transform, torch.nn.Module):
        return BindTorchVisionTransform(transform)

    # bind albumentations transform
    return BindAlbumentationsTransform(transform)


# Pytorch Style Compose
class LandmarksCompose(object):

    def __init__(
            self,
            transforms: List[LandmarksTransform],
            logging: bool = False
    ):
        self.flags: List[bool] = []
        self.transforms: List[LandmarksTransform] = transforms
        self.logging: bool = logging
        assert self.check, "Wrong! Need LandmarksTransform !" \
                           f"But got {self.__repr__()}"

    @property
    def check(self) -> bool:
        return all([isinstance(_, LandmarksTransform) for _ in self.transforms])

    def __call__(
            self,
            img: Image_InOutput_Type,
            landmarks: Landmarks_InOutput_Type
    ) -> Tuple[Image_InOutput_Type, Landmarks_InOutput_Type]:

        self.flags.clear()  # clear each time
        for t in self.transforms:
            try:
                img, landmarks = t(img, landmarks)
            except Exception as e:
                if self.logging:
                    print(f"Error at {t.__class__.__name__} Skip, "
                          f"Flag: {t.flag} Info: {e}")
                continue
            self.flags.append(t.flag)

        return img, landmarks

    def apply_transform_to(
            self,
            other_img: Image_InOutput_Type,
            other_landmarks: Landmarks_InOutput_Type
    ) -> Tuple[Image_InOutput_Type, Landmarks_InOutput_Type]:
        for t, const_flag in zip(self.transforms, self.flags):
            try:
                if const_flag:
                    other_img, other_landmarks = t(other_img, other_landmarks)
            except Exception as e:
                if self.logging:
                    print(f"Error at {t.__class__.__name__} Skip, "
                          f"Flag: {t.flag} Info: {e}")
                continue
        return other_img, other_landmarks

    def apply_affine_to(
            self,
            other_landmarks: Landmarks_InOutput_Type,
            scale: Optional[bool] = True,
            translate: Optional[bool] = True,
            rotate: Optional[bool] = False,
            **kwargs
    ) -> Landmarks_InOutput_Type:
        for t, const_flag in zip(self.transforms, self.flags):
            try:
                if const_flag:
                    other_landmarks = t.apply_affine_to(
                        other_landmarks=other_landmarks,
                        scale=scale,
                        translate=translate,
                        rotate=rotate,
                        **kwargs
                    )
            except Exception as e:
                if self.logging:
                    print(f"Error at {t.__class__.__name__} Skip, "
                          f"Flag: {t.flag} Info: {e}")
                continue
        return other_landmarks

    def clear_affine(self):
        for t in self.transforms:
            t.clear_affine()
        self.flags.clear()

    def __repr__(self) -> str:
        format_string = self.__class__.__name__ + "("
        for t in self.transforms:
            format_string += "\n"
            format_string += f"    {t}"
        format_string += "\n)"
        return format_string


class LandmarksNormalize(LandmarksTransform):
    def __init__(
            self,
            mean: float = 127.5,
            std: float = 128.
    ):
        super(LandmarksNormalize, self).__init__()
        self._mean = mean
        self._std = std

    @autodtye_array
    def __call__(
            self,
            img: np.ndarray,
            landmarks: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        img = img.astype(np.float32)
        img = (img - self._mean) / self._std

        self.flag = True

        return img.astype(np.float32), landmarks.astype(np.float32)


class LandmarksUnNormalize(LandmarksTransform):
    def __init__(
            self,
            mean: float = 127.5,
            std: float = 128.
    ):
        super(LandmarksUnNormalize, self).__init__()

        self._mean = mean
        self._std = std

    @autodtye_array
    def __call__(
            self,
            img: np.ndarray,
            landmarks: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        # must be float
        img = img.astype(np.float32)
        img = img * self._std + self._mean

        self.flag = True

        return img.astype(np.float32), landmarks.astype(np.float32)


class LandmarksToTensor(LandmarksTransform):
    def __init__(self):
        super(LandmarksToTensor, self).__init__()

    @autodtye_array
    def __call__(
            self,
            img: np.ndarray,
            landmarks: np.ndarray
    ) -> Tuple[Tensor, Tensor]:
        # swap color axis because
        # numpy image: H x W x C
        # torch image: C X H X W
        img = img.transpose((2, 0, 1))

        self.flag = True
        return torch.from_numpy(img), torch.from_numpy(landmarks)


class LandmarksToNumpy(LandmarksTransform):
    def __init__(self):
        super(LandmarksToNumpy, self).__init__()

    @autodtye_array
    def __call__(
            self,
            img: Image_InOutput_Type,
            landmarks: Landmarks_InOutput_Type
    ) -> Tuple[np.ndarray, np.ndarray]:
        # C X H X W -> H X W X C
        if landmarks is not None:
            landmarks = landmarks.cpu().numpy() \
                if isinstance(landmarks, Tensor) else landmarks

        if img is not None:
            img = img.cpu().numpy().transpose((1, 2, 0)) \
                if isinstance(img, Tensor) else img.transpose((1, 2, 0))

        self.flag = True

        return img, landmarks


class LandmarksResize(LandmarksTransform):
    """Resize the image in accordance to `image_letter_box` function in darknet
    """

    def __init__(
            self,
            size: Union[Tuple[int, int], int],
            keep_aspect: bool = False
    ):
        super(LandmarksResize, self).__init__()
        if type(size) != tuple:
            if type(size) == int:
                size = (size, size)
            else:
                raise ValueError('size: tuple(int)')

        self._size = size
        self._keep_aspect = keep_aspect

        if self._keep_aspect:
            self._letterbox_image_func = F.letterbox_image
        else:
            self._letterbox_image_func = F.letterbox_image_v2

    @autodtye_array
    def __call__(
            self,
            img: np.ndarray,
            landmarks: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:

        w, h = img.shape[1], img.shape[0]  # original shape
        new_img = self._letterbox_image_func(img.copy().astype(np.uint8), self._size)

        num_landmarks = len(landmarks)
        landmark_bboxes = F.landmarks_tool.project_to_bboxes(landmarks)

        if self._keep_aspect:
            scale = min(self._size[1] / h, self._size[0] / w)
            landmark_bboxes[:, :4] *= scale

            new_w = scale * w
            new_h = scale * h
            # inp_dim = self.inp_dim
            inp_dim_w, inp_dim_h = self._size

            del_h = (inp_dim_h - new_h) // 2
            del_w = (inp_dim_w - new_w) // 2

            add_matrix = np.array([[del_w, del_h, del_w, del_h]], dtype=landmark_bboxes.dtype)

            landmark_bboxes[:, :4] += add_matrix
            # refine according to new shape
            new_landmarks = F.landmarks_tool.reproject_to_landmarks(landmark_bboxes,
                                                                    img_w=new_img.shape[1],
                                                                    img_h=new_img.shape[0])

            self.scale_x = scale
            self.scale_y = scale
        else:
            scale_y, scale_x = self._size[1] / h, self._size[0] / w
            landmark_bboxes[:, (0, 2)] *= scale_x
            landmark_bboxes[:, (1, 3)] *= scale_y

            # refine according to new shape
            new_landmarks = F.landmarks_tool.reproject_to_landmarks(landmark_bboxes,
                                                                    img_w=new_img.shape[1],
                                                                    img_h=new_img.shape[0])
            self.scale_x = scale_x
            self.scale_y = scale_y

        if len(new_landmarks) != num_landmarks:
            raise F.LandmarkMissError('LandmarksResize: {0} input landmarks, but got {1} output '
                                      'landmarks'.format(num_landmarks, len(new_landmarks)))

        self.flag = True

        return new_img.astype(np.uint8), new_landmarks.astype(np.float32)


class LandmarksClip(LandmarksTransform):
    """Get the five sense organs clipping image and landmarks"""

    def __init__(
            self,
            width_pad: float = 0.2,
            height_pad: float = 0.2,
            target_size: Union[Tuple[int, int], int] = None,
            **kwargs
    ):
        """Clip enclosure box according the given landmarks.
        :param width_pad: the padding ration to extend the width of clipped box.
        :param height_pad: the padding ration to extend the height of clipped box.
        :param target_size: target size for resize operation.
        """
        super(LandmarksClip, self).__init__()
        self._width_pad = width_pad
        self._height_pad = height_pad
        self._target_size = target_size

        if self._target_size is not None:
            if isinstance(self._target_size, int) or isinstance(self._target_size, tuple):
                if isinstance(self._target_size, int):
                    self._target_size = (self._target_size, self._target_size)
                if isinstance(self._target_size, tuple):
                    assert len(self._target_size) == 2
            else:
                raise ValueError('wrong target size, should be (w,h)')

            self._resize_op = LandmarksResize(self._target_size, **kwargs)
        else:
            self._resize_op = None

    @autodtye_array
    def __call__(
            self,
            img: np.ndarray,
            landmarks: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        :param img:
        :param landmarks: [num, 2]
        :return:
        """
        x_min = np.min(landmarks[:, 0])
        x_max = np.max(landmarks[:, 0])
        y_min = np.min(landmarks[:, 1])
        y_max = np.max(landmarks[:, 1])

        h, w = img.shape[0], img.shape[1]

        lh, lw = abs(y_max - y_min), abs(x_max - x_min)

        # 一定会包含所有的点位
        left = np.maximum(int(x_min) - int(lw * self._width_pad), 0)
        right = np.minimum(int(x_max) + int(lw * self._width_pad), w)
        top = np.maximum(int(y_min) - int(lh * self._height_pad), 0)
        bottom = np.minimum(int(y_max) + int(lh * self._height_pad), h)

        new_img = img[top:bottom, left:right, :].copy()
        new_landmarks = landmarks.copy()

        new_landmarks[:, 0] -= left
        new_landmarks[:, 1] -= top

        if self._resize_op is not None:
            new_img, new_landmarks, _ = self._resize_op(new_img, new_landmarks)
            self.scale_x = self._resize_op.scale_x
            self.scale_y = self._resize_op.scale_y

        self.flag = True

        return new_img.astype(np.uint8), new_landmarks.astype(np.float32)


class LandmarksAlign(LandmarksTransform):
    """Get alignment image and landmarks"""

    def __init__(
            self,
            eyes_index: Union[Tuple[int, int], List[int]] = None
    ):
        """
        :param eyes_index: 2 indexes in landmarks,
            which indicates left and right eye center.
        """
        super(LandmarksAlign, self).__init__()
        if eyes_index is None or len(eyes_index) != 2:
            raise ValueError("2 indexes in landmarks, "
                             "which indicates left and right eye center.")

        self._eyes_index = eyes_index

    @autodtye_array
    def __call__(
            self,
            img: np.ndarray,
            landmarks: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:

        left_eye = landmarks[self._eyes_index[0]]  # left eye
        right_eye = landmarks[self._eyes_index[1]]  # right eye
        dx = (right_eye[0] - left_eye[0])  # right - left
        dy = (right_eye[1] - left_eye[1])
        angle = math.atan2(dy, dx) * 180 / math.pi  # 计算角度

        num_landmarks = len(landmarks)
        landmark_bboxes = F.landmarks_tool.project_to_bboxes(landmarks)

        w, h = img.shape[1], img.shape[0]
        cx, cy = w // 2, h // 2

        new_img = F.rotate_im(img.copy(), angle)

        landmarks_corners = F.get_corners(landmark_bboxes)

        landmarks_corners = np.hstack((landmarks_corners, landmark_bboxes[:, 4:]))

        landmarks_corners[:, :8] = F.rotate_box(landmarks_corners[:, :8], angle, cx, cy, h, w)

        new_landmark_bbox = np.zeros_like(landmark_bboxes)
        new_landmark_bbox[:, [0, 1]] = landmarks_corners[:, [0, 1]]
        new_landmark_bbox[:, [2, 3]] = landmarks_corners[:, [6, 7]]

        scale_factor_x = new_img.shape[1] / w

        scale_factor_y = new_img.shape[0] / h

        new_img = cv2.resize(new_img, (w, h))

        new_landmark_bbox[:, :4] /= [scale_factor_x, scale_factor_y, scale_factor_x, scale_factor_y]

        landmark_bboxes = new_landmark_bbox[:, :]

        landmark_bboxes = F.clip_box(landmark_bboxes, [0, 0, w, h], 0.0025)
        # refine according to new shape
        new_landmarks = F.landmarks_tool.reproject_to_landmarks(landmark_bboxes,
                                                                img_w=new_img.shape[1],
                                                                img_h=new_img.shape[0])

        self.scale_x = (1 / scale_factor_x)
        self.scale_y = (1 / scale_factor_y)

        if len(new_landmarks) != num_landmarks:
            raise F.LandmarkMissError('LandmarksAlign: {0} input landmarks, but got {1} output '
                                      'landmarks'.format(num_landmarks, len(new_landmarks)))

        self.flag = True

        return new_img.astype(np.uint8), new_landmarks.astype(np.float32)


class LandmarksRandomCenterCrop(LandmarksTransform):
    def __init__(
            self,
            width_range: Tuple[float, float] = (0.8, 1.0),
            height_range: Tuple[float, float] = (0.8, 1.0),
            prob: float = 0.5
    ):
        super(LandmarksRandomCenterCrop, self).__init__()
        self._width_range = width_range
        self._height_range = height_range
        self._prob = prob

    @autodtye_array
    def __call__(
            self,
            img: np.ndarray,
            landmarks: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:

        if np.random.uniform(0., 1.) > self._prob:
            self.clear_affine()
            return img.astype(np.uint8), landmarks.astype(np.float32)

        height, width, _ = img.shape
        cx, cy = int(width / 2), int(height / 2)

        # 点位越界
        x_min = np.min(landmarks[:, 0])
        x_max = np.max(landmarks[:, 0])
        y_min = np.min(landmarks[:, 1])
        y_max = np.max(landmarks[:, 1])

        height_ratio = np.random.uniform(self._height_range[0], self._height_range[1], size=1)
        width_ratio = np.random.uniform(self._width_range[0], self._width_range[1], size=1)
        # 四周是随机的 不是均匀的 可能左宽右窄 也可能上宽下窄 随机
        top_height_ratio = np.random.uniform(0.4, 0.6)
        left_width_ratio = np.random.uniform(0.4, 0.6)

        crop_height = min(int(height_ratio * height + 1), height)
        crop_width = min(int(width_ratio * width + 1), width)

        left_width_offset = crop_width * left_width_ratio
        right_width_offset = crop_width - left_width_offset
        top_height_offset = crop_height * top_height_ratio
        bottom_height_offset = crop_height - top_height_offset

        x1 = max(0, int(cx - left_width_offset + 1))
        x2 = min(width, int(cx + right_width_offset))
        y1 = max(0, int(cy - top_height_offset + 1))
        y2 = min(height, int(cy + bottom_height_offset))

        x1 = max(int(min(x1, x_min)), 0)
        x2 = min(int(max(x2, x_max + 1)), width)
        y1 = max(int(min(y1, y_min)), 0)
        y2 = min(int(max(y2, y_max + 1)), height)

        crop_width = abs(x2 - x1)
        crop_height = abs(y2 - y1)

        new_landmarks = landmarks.copy()
        new_landmarks[:, 0] -= x1
        new_landmarks[:, 1] -= y1

        # 点位越界检查
        lx_min = np.min(new_landmarks[:, 0])
        lx_max = np.max(new_landmarks[:, 0])
        ly_min = np.min(new_landmarks[:, 1])
        ly_max = np.max(new_landmarks[:, 1])

        if any((lx_min < 0., lx_max > crop_width, ly_min < 0., ly_max > crop_height)):
            return img.astype(np.uint8), landmarks

        new_img = img[y1:y2, x1:x2, :].copy()

        self.flag = True

        return new_img.astype(np.uint8), new_landmarks.astype(np.float32)


class LandmarksRandomHorizontalFlip(LandmarksTransform):
    """Randomly horizontally flips the Image with the probability *prob*
    """

    def __init__(
            self,
            prob: float = 0.5
    ):
        super(LandmarksRandomHorizontalFlip, self).__init__()
        self._prob = prob

    @autodtye_array
    def __call__(
            self,
            img: np.ndarray,
            landmarks: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        :param img: original img contain in 3-d numpy.ndarray. [HxWxC]
        :param landmarks: 2-d numpy.ndarray [num_landmarks, 2] (x1, y1)
        :return:
        """
        if np.random.uniform(0., 1.) > self._prob:
            self.clear_affine()
            return img.astype(np.uint8), landmarks.astype(np.float32)

        h, w, _ = img.shape
        cx = float(w / 2)
        new_img = img[:, ::-1, :].copy()
        # TODO: 点位的索引位置也需要进行相应的改变
        # 若x1<cx，则x1_flip=x1+2*(cx-x1)；若x1>cx，x1_flip=x1-2*(x1-cx)=x1+2*(cx-x1)
        new_landmarks = landmarks.copy()
        new_landmarks[:, 0] += 2 * (cx - new_landmarks[:, 0])

        self.flag = True

        return new_img.astype(np.uint8), new_landmarks.astype(np.float32)


class LandmarksHorizontalFlip(LandmarksTransform):
    """Randomly horizontally flips the Image
    """

    def __init__(self):
        super(LandmarksHorizontalFlip, self).__init__()

    @autodtye_array
    def __call__(
            self,
            img: np.ndarray,
            landmarks: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        h, w, _ = img.shape
        cx = float(w / 2)
        new_img = img[:, ::-1, :].copy()
        # TODO: 点位的索引位置也需要进行相应的改变
        # 若x1<cx，则x1_flip=x1+2*(cx-x1)；若x1>cx，x1_flip=x1-2*(x1-cx)=x1+2*(cx-x1)
        new_landmarks = landmarks.copy()
        new_landmarks[:, 0] += 2 * (cx - new_landmarks[:, 0])

        self.flag = True

        return new_img.astype(np.uint8), new_landmarks.astype(np.float32)


class LandmarksRandomScale(LandmarksTransform):
    """Randomly scales an image with landmarks
    """

    def __init__(
            self,
            scale: Union[Tuple[float, float], float] = 0.4,
            prob: float = 0.5,
            diff: bool = True
    ):
        super(LandmarksRandomScale, self).__init__()
        self._scale = scale
        self._prob = prob

        if isinstance(self._scale, tuple):
            assert len(self._scale) == 2., "Invalid range"
            assert self._scale[0] > -1., "Scale factor can't be less than -1"
            assert self._scale[1] > -1., "Scale factor can't be less than -1"
        elif isinstance(self._scale, float):
            assert self._scale > 0., "Please input a positive float"
            self._scale = (max(-1., -self._scale), self._scale)

        self._diff = diff

    @autodtye_array
    def __call__(
            self,
            img: np.ndarray,
            landmarks: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:

        if np.random.uniform(0., 1.) > self._prob:
            self.clear_affine()
            return img.astype(np.uint8), landmarks.astype(np.float32)

        # Chose a random digit to scale by
        num_landmarks = len(landmarks)
        new_landmarks = landmarks.copy()

        if self._diff:
            scale_x = random.uniform(*self._scale)
            scale_y = random.uniform(*self._scale)
        else:
            scale_x = random.uniform(*self._scale)
            scale_y = scale_x

        resize_scale_x = 1 + scale_x
        resize_scale_y = 1 + scale_y

        new_img = cv2.resize(img, None, fx=resize_scale_x, fy=resize_scale_y)

        new_landmarks[:, 0] *= resize_scale_x
        new_landmarks[:, 1] *= resize_scale_y

        self.scale_x = resize_scale_x
        self.scale_y = resize_scale_y

        if len(new_landmarks) != num_landmarks:
            raise F.LandmarkMissError('LandmarksRandomScale: {0} input landmarks, but got {1} output '
                                      'landmarks'.format(num_landmarks, len(new_landmarks)))

        self.flag = True

        return new_img.astype(np.uint8), new_landmarks.astype(np.float32)


class LandmarksRandomTranslate(LandmarksTransform):
    """Randomly Translates the image with landmarks
    """

    def __init__(
            self,
            translate: Union[Tuple[float, float], float] = 0.2,
            prob: float = 0.5,
            diff: bool = False
    ):
        super(LandmarksRandomTranslate, self).__init__()
        self._translate = translate
        self._prob = prob

        if type(self._translate) == tuple:
            if len(self._translate) != 2:
                raise ValueError('len(self.translate) == 2, Invalid range')
            if self._translate[0] <= -1. or self._translate[0] >= 1.:
                raise ValueError('out of range (-1,1)')
            if self._translate[1] <= -1. or self._translate[1] >= 1.:
                raise ValueError('out of range (-1,1)')
            self._translate = (min(self._translate), max(self._translate))
        elif type(self._translate) == float:
            if self._translate <= -1. or self._translate >= 1.:
                raise ValueError('out of range (-1,1)')
            self._translate = (
                min(-self._translate, self._translate),
                max(-self._translate, self._translate)
            )
        else:
            raise ValueError('out of range (-1,1)')

        self._diff = diff

    @autodtye_array
    def __call__(
            self,
            img: np.ndarray,
            landmarks: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:

        if np.random.uniform(0., 1.) > self._prob:
            self.clear_affine()
            return img.astype(np.uint8), landmarks.astype(np.float32)

        # Chose a random digit to scale by
        img_shape = img.shape
        num_landmarks = len(landmarks)
        landmark_bboxes = F.landmarks_tool.project_to_bboxes(landmarks)
        # translate the image

        # percentage of the dimension of the image to translate
        translate_factor_x = random.uniform(*self._translate)
        translate_factor_y = random.uniform(*self._translate)

        if not self._diff:
            translate_factor_y = translate_factor_x

        canvas = np.zeros(img_shape).astype(np.uint8)

        corner_x = int(translate_factor_x * img.shape[1])
        corner_y = int(translate_factor_y * img.shape[0])

        # change the origin to the top-left corner of the translated box
        orig_box_cords = [max(0, corner_y), max(corner_x, 0),
                          min(img_shape[0], corner_y + img.shape[0]),
                          min(img_shape[1], corner_x + img.shape[1])]

        mask = img[max(-corner_y, 0):min(img.shape[0], -corner_y + img_shape[0]),
               max(-corner_x, 0):min(img.shape[1], -corner_x + img_shape[1]), :]

        canvas[orig_box_cords[0]:orig_box_cords[2], orig_box_cords[1]:orig_box_cords[3], :] = mask
        new_img = canvas

        landmark_bboxes[:, :4] += [corner_x, corner_y, corner_x, corner_y]

        landmark_bboxes = F.clip_box(landmark_bboxes, [0, 0, img_shape[1], img_shape[0]], 0.0025)
        # refine according to new shape
        new_landmarks = F.landmarks_tool.reproject_to_landmarks(landmark_bboxes,
                                                                img_w=new_img.shape[1],
                                                                img_h=new_img.shape[0])

        if len(new_landmarks) != num_landmarks:
            raise F.LandmarkMissError(
                'LandmarksRandomTranslate: {0} input landmarks, but got {1} output '
                'landmarks'.format(num_landmarks, len(new_landmarks))
            )

        # TODO: add translate affine records
        self.flag = True

        return new_img.astype(np.uint8), new_landmarks.astype(np.float32)


class LandmarksRandomRotate(LandmarksTransform):
    """Randomly rotates an image with landmarks
    """

    def __init__(
            self,
            angle: Union[Tuple[int, int], List[int], int] = 10,
            prob: float = 0.5,
            bins: Optional[int] = None
    ):
        super(LandmarksRandomRotate, self).__init__()
        self._angle = angle
        self._bins = bins
        self._prob = prob

        if type(self._angle) == tuple or type(self._angle) == list:
            assert len(self._angle) == 2, "Invalid range"
            self._angle = (min(self._angle), max(self._angle))
        else:
            self._angle = (
                min(-self._angle, self._angle),
                max(-self._angle, self._angle)
            )
        if self._bins is not None and isinstance(self._bins, int):
            interval = int(abs(self._angle[1] - self._angle[0]) / self._bins) + 1
            self.choose_angles = list(range(self._angle[0], self._angle[1], interval))
        else:
            interval = int(abs(self._angle[1] - self._angle[0]))
            self.choose_angles = np.random.uniform(*self._angle, size=interval)

    @autodtye_array
    def __call__(
            self,
            img: np.ndarray,
            landmarks: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:

        if np.random.uniform(0., 1.0) > self._prob:
            self.clear_affine()
            return img.astype(np.uint8), landmarks.astype(np.float32)

        angle = np.random.choice(self.choose_angles)
        num_landmarks = len(landmarks)
        landmark_bboxes = F.landmarks_tool.project_to_bboxes(landmarks)

        w, h = img.shape[1], img.shape[0]
        cx, cy = w // 2, h // 2

        new_img = F.rotate_im(img.copy(), angle)

        landmarks_corners = F.get_corners(landmark_bboxes)

        landmarks_corners = np.hstack((landmarks_corners, landmark_bboxes[:, 4:]))

        landmarks_corners[:, :8] = F.rotate_box(landmarks_corners[:, :8], angle, cx, cy, h, w)

        new_landmark_bbox = np.zeros_like(landmark_bboxes)
        new_landmark_bbox[:, [0, 1]] = landmarks_corners[:, [0, 1]]
        new_landmark_bbox[:, [2, 3]] = landmarks_corners[:, [6, 7]]

        scale_factor_x = new_img.shape[1] / w

        scale_factor_y = new_img.shape[0] / h

        new_img = cv2.resize(new_img, (w, h))

        new_landmark_bbox[:, :4] /= [scale_factor_x, scale_factor_y, scale_factor_x, scale_factor_y]

        landmark_bboxes = new_landmark_bbox[:, :]

        landmark_bboxes = F.clip_box(landmark_bboxes, [0, 0, w, h], 0.0025)
        # refine according to new shape
        new_landmarks = F.landmarks_tool.reproject_to_landmarks(landmark_bboxes,
                                                                img_w=new_img.shape[1],
                                                                img_h=new_img.shape[0])
        self.scale_x = (1 / scale_factor_x)
        self.scale_y = (1 / scale_factor_y)

        if len(new_landmarks) != num_landmarks:
            raise F.LandmarkMissError(
                'LandmarksRandomRotate: {0} input landmarks, but got {1} output '
                'landmarks'.format(num_landmarks, len(new_landmarks))
            )

        # TODO: add rotate affine records
        self.flag = True

        return new_img.astype(np.uint8), new_landmarks.astype(np.float32)


class LandmarksRandomShear(LandmarksTransform):
    """Randomly shears an image in horizontal direction
    """

    def __init__(
            self,
            shear_factor: Union[Tuple[float, float], List[float], float] = 0.2,
            prob: float = 0.5
    ):
        super(LandmarksRandomShear, self).__init__()
        self._shear_factor = shear_factor
        self._prob = prob

        if type(self._shear_factor) == tuple \
                or type(self._shear_factor) == list:
            assert len(self._shear_factor) == 2, "Invalid range for scaling factor"
        else:
            self._shear_factor = (
                min(-self._shear_factor, self._shear_factor),
                max(-self._shear_factor, self._shear_factor)
            )

        # shear_factor = random.uniform(*self.shear_factor)

    @autodtye_array
    def __call__(
            self,
            img: np.ndarray,
            landmarks: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:

        if np.random.uniform(0., 1.) > self._prob:
            self.clear_affine()
            return img.astype(np.uint8), landmarks.astype(np.float32)

        num_landmarks = len(landmarks)
        shear_factor = random.uniform(*self._shear_factor)

        w, h = img.shape[1], img.shape[0]

        new_img = img.copy()
        new_landmarks = landmarks.copy()

        if shear_factor < 0:
            new_img, new_landmarks = LandmarksHorizontalFlip()(new_img, new_landmarks)

        landmark_bboxes = F.landmarks_tool.project_to_bboxes(new_landmarks)

        M = np.array([[1, abs(shear_factor), 0], [0, 1, 0]])

        nW = new_img.shape[1] + abs(shear_factor * new_img.shape[0])

        landmark_bboxes[:, [0, 2]] += ((landmark_bboxes[:, [1, 3]]) * abs(shear_factor)).astype(int)

        new_img = cv2.warpAffine(new_img, M, (int(nW), new_img.shape[0]))
        new_landmarks = F.landmarks_tool.reproject_to_landmarks(landmark_bboxes)

        if shear_factor < 0:
            new_img, new_landmarks = LandmarksHorizontalFlip()(new_img, new_landmarks)

        landmark_bboxes = F.landmarks_tool.project_to_bboxes(new_landmarks)
        new_img = cv2.resize(new_img, (w, h))

        scale_factor_x = nW / w

        landmark_bboxes[:, :4] /= [scale_factor_x, 1, scale_factor_x, 1]
        # refine according to new shape
        new_landmarks = F.landmarks_tool.reproject_to_landmarks(landmark_bboxes,
                                                                img_w=new_img.shape[1],
                                                                img_h=new_img.shape[0])

        self.scale_x = (1. / scale_factor_x)
        self.scale_y = 1.

        if len(new_landmarks) != num_landmarks:
            raise F.LandmarkMissError(
                'LandmarksRandomShear: {0} input landmarks, but got {1} output '
                'landmarks'.format(num_landmarks, len(new_landmarks))
            )

        self.flag = True

        return new_img.astype(np.uint8), new_landmarks.astype(np.float32)


class LandmarksRandomHSV(LandmarksTransform):
    """HSV Transform to vary hue saturation and brightness

    Hue has a range of 0-179
    Saturation and Brightness have a range of 0-255.
    Chose the amount you want to change thhe above quantities accordingly.


    Parameters
    ----------
    hue : None or int or tuple (int)
        If None, the hue of the image is left unchanged. If int,
        a random int is uniformly sampled from (-hue, hue) and added to the
        hue of the image. If tuple, the int is sampled from the range
        specified by the tuple.

    saturation : None or int or tuple(int)
        If None, the saturation of the image is left unchanged. If int,
        a random int is uniformly sampled from (-saturation, saturation)
        and added to the hue of the image. If tuple, the int is sampled
        from the range  specified by the tuple.

    brightness : None or int or tuple(int)
        If None, the brightness of the image is left unchanged. If int,
        a random int is uniformly sampled from (-brightness, brightness)
        and added to the hue of the image. If tuple, the int is sampled
        from the range  specified by the tuple.
    """

    def __init__(
            self,
            hue: Union[Tuple[int, int], int] = None,
            saturation: Union[Tuple[int, int], int] = None,
            brightness: Union[Tuple[int, int], int] = None,
            prob: float = 0.5
    ):
        super(LandmarksRandomHSV, self).__init__()
        self._prob = prob
        self._hue = hue if hue else 0
        self._saturation = saturation if saturation else 0
        self._brightness = brightness if brightness else 0

        if type(self._hue) != tuple:
            self._hue = (min(-self._hue, self._hue), max(-self._hue, self._hue))
        if type(self._saturation) != tuple:
            self._saturation = (min(-self._saturation, self._saturation),
                                max(-self._saturation, self._saturation))
        if type(self._brightness) != tuple:
            self._brightness = (min(-self._brightness, self._brightness),
                                max(-self._brightness, self._brightness))

    @autodtye_array
    def __call__(
            self,
            img: np.ndarray,
            landmarks: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:

        if np.random.uniform(0., 1.) > self._prob:
            self.clear_affine()
            return img.astype(np.uint8), landmarks.astype(np.float32)

        hue = random.randint(*self._hue)
        saturation = random.randint(*self._saturation)
        brightness = random.randint(*self._brightness)

        new_img = img.copy()

        a = np.array([hue, saturation, brightness]).astype(np.uint8)
        new_img += np.reshape(a, (1, 1, 3))

        new_img = np.clip(new_img, 0, 255)
        new_img[:, :, 0] = np.clip(new_img[:, :, 0], 0, 179)

        new_img = new_img.astype(np.uint8)

        self.flag = True

        return new_img.astype(np.uint8), landmarks.astype(np.float32)


class LandmarksRandomMask(LandmarksTransform):
    """Implement of Random-Mask data augment for performance improving
    of the occlusion object in landmarks-detection."""

    # Note: 需要考虑Mask对点位可见性的影响，被mask的区域点位不可见
    def __init__(
            self,
            mask_ratio: float = 0.25,
            prob: float = 0.5,
            trans_ratio: float = 0.5
    ):
        """random select a mask ratio.
        :param mask_ratio: control the ratio of area to mask, must >= 0.1.
        :param prob:
        :param trans_ratio: control the random shape of masked area.
        """
        super(LandmarksRandomMask, self).__init__()
        assert 0.10 < mask_ratio < 1.
        assert 0 < trans_ratio < 1.
        self._mask_ratio = mask_ratio
        self._trans_ratio = trans_ratio
        self._prob = prob

    @autodtye_array
    def __call__(
            self,
            img: np.ndarray,
            landmarks: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        if np.random.uniform(0., 1.0) > self._prob:
            self.clear_affine()
            return img.astype(np.uint8), landmarks.astype(np.float32)

        w, h = img.shape[1], img.shape[0]  # original shape
        # 被mask的面积是随机的
        mask_ratio = np.random.uniform(0.05, self._mask_ratio, size=1)
        mask_ratio = np.sqrt(mask_ratio)
        mask_h, mask_w = int(h * mask_ratio), int(w * mask_ratio)
        delta = mask_h * mask_w
        # 被mask的形状是随机的
        down_w = max(2, int(mask_w * self._trans_ratio))
        up_w = min(int(mask_w * (1 + self._trans_ratio)), w - 2)
        new_mask_w = np.random.randint(min(down_w, up_w), max(down_w, up_w))
        new_mask_h = int(delta / new_mask_w)

        # 被mask的位置是随机的
        new_img, mask_corner = F.random_mask_img(img.copy(), new_mask_w, new_mask_h)

        self.flag = True

        return new_img.astype(np.uint8), landmarks.astype(np.float32)


class LandmarksRandomBlur(LandmarksTransform):
    """Gaussian Blur"""

    def __init__(
            self,
            kernel_range: Tuple[int, int] = (3, 11),
            prob: float = 0.5,
            sigma_range: Tuple[int, int] = (0, 4)
    ):
        """
        :param kernel_range: kernels for cv2.blur
        :param prob: control the random shape of masked area.
        """
        super(LandmarksRandomBlur, self).__init__()
        self._prob = prob
        self._kernel_range = list(range(kernel_range[0], kernel_range[1] + 1))
        self._kernel_range = [x for x in self._kernel_range if (x % 2) != 0]  # 奇数
        self._sigma_range = sigma_range

    @autodtye_array
    def __call__(
            self,
            img: np.ndarray,
            landmarks: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        if np.random.uniform(0., 1.) > self._prob:
            self.clear_affine()
            return img.astype(np.uint8), landmarks.astype(np.float32)

        kernel = np.random.choice(self._kernel_range)
        sigmaX = np.random.choice(self._sigma_range)
        sigmaY = np.random.choice(self._sigma_range)

        img_blur = cv2.GaussianBlur(img.copy(), (kernel, kernel), sigmaX=sigmaX, sigmaY=sigmaY)

        self.flag = True

        return img_blur.astype(np.uint8), landmarks.astype(np.float32)


class LandmarksRandomBrightness(LandmarksTransform):
    """Brightness Transform
        Parameters
        ----------
        brightness : None or int or tuple(int)
            If None, the brightness of the image is left unchanged. If int,
            a random int is uniformly sampled from (-brightness, brightness)
            and added to the hue of the image. If tuple, the int is sampled
            from the range  specified by the tuple.

        """

    def __init__(
            self,
            brightness: Tuple[float, float] = (-30., 30.),
            contrast: Tuple[float, float] = (0.5, 1.5),
            prob: float = 0.5
    ):
        super(LandmarksRandomBrightness, self).__init__()
        self._prob = prob
        if type(brightness) != tuple:
            raise ValueError
        if type(contrast) != tuple:
            raise ValueError

        self.contrast = np.linspace(contrast[0], contrast[1], num=30)
        self.brightness = np.linspace(brightness[0], brightness[1], num=60)

    @autodtye_array
    def __call__(
            self,
            img: np.ndarray,
            landmarks: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        if np.random.uniform(0., 1.) > self._prob:
            self.clear_affine()
            return img.astype(np.uint8), landmarks.astype(np.float32)

        brightness = np.random.choice(self.brightness)
        contrast = np.random.choice(self.contrast)

        img = img.astype(np.float32)
        img = contrast * img + brightness
        img = np.clip(img, 0, 255)

        self.flag = True

        return img.astype(np.uint8), landmarks.astype(np.float32)


class LandmarksRandomPatches(LandmarksTransform):
    """Implement of Random-Patch data augment for performance improving
    of the occlusion object in landmarks-detection. 从随机选择的图片上
    随机crop一块, 对输入的人脸图片进行patch，模拟人脸被物体的遮挡. 该方法直接
    没有使用Alpha进行融合. Alpha融合需要获取遮挡物的mask，或者直接使用addWeighted"""

    def __init__(
            self,
            patch_ratio: float = 0.15,
            prob: float = 0.5,
            trans_ratio: float = 0.5
    ):
        """random select a patch ratio.
        :param patch_ratio: control the ratio of area to patch, must >= 0.1.
        :param prob:
        :param trans_ratio: control the random shape of patched area.
        """
        super(LandmarksRandomPatches, self).__init__()
        assert 0.10 < patch_ratio < 1.
        assert 0 < trans_ratio < 1.
        self._patch_ratio = patch_ratio
        self._trans_ratio = trans_ratio
        self._prob = prob
        self._patches_paths = []
        self._patches_root = Path(__file__).parent
        self._patches_dirs = [
            os.path.join(self._patches_root, "patches/hands"),  # 手掌
            os.path.join(self._patches_root, "patches/hats"),  # 帽子
            os.path.join(self._patches_root, "patches/clothes"),  # 衣服
            os.path.join(self._patches_root, "patches/masks"),  # 口罩
            os.path.join(self._patches_root, "patches/others")  # 其他背景
        ]
        self._init_patches_paths()

    @autodtye_array
    def __call__(
            self,
            img: np.ndarray,
            landmarks: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:

        if np.random.uniform(0., 1.0) > self._prob:
            self.clear_affine()
            return img.astype(np.uint8), landmarks.astype(np.float32)

        w, h = img.shape[1], img.shape[0]  # original shape
        # 被patch的面积是随机的
        patch_ratio = np.random.uniform(0.05, self._patch_ratio, size=1)
        patch_ratio = np.sqrt(patch_ratio)
        patch_h, patch_w = int(h * patch_ratio), int(w * patch_ratio)
        delta = patch_h * patch_w
        # 被patch的形状是随机的矩形
        down_w = max(2, int(patch_w * self._trans_ratio))
        up_w = min(int(patch_w * (1 + self._trans_ratio)), w - 2)
        new_patch_w = np.random.randint(min(down_w, up_w), max(down_w, up_w))
        new_patch_h = int(delta / new_patch_w)

        # 被patch的位置是随机的
        patch = self._random_select_patch(patch_h=new_patch_h, patch_w=new_patch_w)
        if patch is None:
            self.flag = True
            img.astype(np.uint8), landmarks.astype(np.float32)

        new_img, patch_corner = self._random_patch_img(img=img, patch=patch)
        self.flag = True

        return new_img.astype(np.uint8), landmarks.astype(np.float32)

    def _init_patches_paths(self):
        self._patches_paths.clear()
        for d in self._patches_dirs:
            files = [x for x in os.listdir(d) if
                     any((x.lower().endswith("jpeg"),
                          x.lower().endswith("jpg"),
                          x.lower().endswith("png")))]

            paths = [os.path.join(d, x) for x in files]
            self._patches_paths.extend(paths)

    def _random_select_patch(
            self,
            patch_h: int = 32,
            patch_w: int = 32
    ) -> Union[np.ndarray, None]:

        patch_path = np.random.choice(self._patches_paths)
        patch_img = cv2.imread(patch_path)
        if patch_img is None:
            return None
        h, w, _ = patch_img.shape
        if h <= patch_h or w <= patch_w:
            patch = cv2.resize(patch_img, (patch_w, patch_h))
            return patch
        x1 = np.random.randint(0, w - patch_w + 1)
        y1 = np.random.randint(0, h - patch_h + 1)
        x2 = x1 + patch_w
        y2 = y1 + patch_h
        patch = patch_img[y1:y2, x1:x2, :]

        return patch

    @staticmethod
    def _random_patch_img(
            img: np.ndarray,
            patch: np.ndarray
    ) -> Tuple[np.ndarray, List[int]]:
        h, w, c = img.shape
        patch_h, patch_w, _ = patch.shape
        patch_w = min(max(0., patch_w), w)
        patch_h = min(max(0., patch_h), h)
        x0 = np.random.randint(0, w - patch_w + 1)
        y0 = np.random.randint(0, h - patch_h + 1)
        x1, y1 = int(x0 + patch_w), int(y0 + patch_h)
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, w), min(y1, h)
        img[y0:y1, x0:x1, :] = patch[:, :, :]
        patch_corner = [x0, y0, x1, y1]

        return img.astype(np.uint8), patch_corner


class LandmarksRandomPatchesWithAlpha(LandmarksTransform):
    """Implement of Random-Patch data augment for performance improving
    of the occlusion object in landmarks-detection. 从随机选择的图片上
    随机crop一块, 对输入的人脸图片进行patch，模拟人脸被物体的遮挡."""

    def __init__(
            self,
            patch_ratio: float = 0.2,
            prob: float = 0.5,
            trans_ratio: float = 0.5,
            alpha: float = 0.9
    ):
        """random select a patch ratio.
        :param patch_ratio: control the ratio of area to patch, must >= 0.1.
        :param prob:
        :param trans_ratio: control the random shape of patched area.
        :param alpha: max alpha value.
        """
        super(LandmarksRandomPatchesWithAlpha, self).__init__()
        assert 0.10 < patch_ratio < 1.
        assert 0 < trans_ratio < 1.
        self._patch_ratio = patch_ratio
        self._trans_ratio = trans_ratio
        self._prob = prob
        self._alpha = alpha
        assert 0. <= alpha <= 1.0
        self._patches_paths = []
        self._patches_root = Path(__file__).parent
        self._patches_dirs = [
            os.path.join(self._patches_root, "patches/hands"),  # 手掌
            os.path.join(self._patches_root, "patches/hats"),  # 帽子
            os.path.join(self._patches_root, "patches/clothes"),  # 衣服
            os.path.join(self._patches_root, "patches/masks"),  # 口罩
            os.path.join(self._patches_root, "patches/others")  # 其他背景
        ]
        self._init_patches_paths()

    @autodtye_array
    def __call__(
            self,
            img: np.ndarray,
            landmarks: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:

        if np.random.uniform(0., 1.0) > self._prob:
            self.clear_affine()
            return img.astype(np.uint8), landmarks.astype(np.float32)

        w, h = img.shape[1], img.shape[0]  # original shape
        # 被patch的面积是随机的
        patch_ratio = np.random.uniform(0.05, self._patch_ratio, size=1)
        patch_ratio = np.sqrt(patch_ratio)
        patch_h, patch_w = int(h * patch_ratio), int(w * patch_ratio)
        delta = patch_h * patch_w
        # 被patch的形状是随机的矩形
        down_w = max(2, int(patch_w * self._trans_ratio))
        up_w = min(int(patch_w * (1 + self._trans_ratio)), w - 2)
        new_patch_w = np.random.randint(min(down_w, up_w), max(down_w, up_w))
        new_patch_h = int(delta / new_patch_w)

        # 被patch的位置是随机的
        patch = self._random_select_patch(patch_h=new_patch_h, patch_w=new_patch_w)
        if patch is None:
            self.flag = True
            img.astype(np.uint8), landmarks.astype(np.float32)

        alpha = np.random.uniform(0.1, self._alpha)
        new_img, patch_corner = self._random_patch_img_with_alpha(img=img, patch=patch, alpha=alpha)

        self.flag = True

        return new_img.astype(np.uint8), landmarks.astype(np.float32)

    def _init_patches_paths(self):
        self._patches_paths.clear()
        for d in self._patches_dirs:
            files = [x for x in os.listdir(d) if
                     any((x.lower().endswith("jpeg"),
                          x.lower().endswith("jpg"),
                          x.lower().endswith("png")))]

            paths = [os.path.join(d, x) for x in files]
            self._patches_paths.extend(paths)

    def _random_select_patch(
            self,
            patch_h: int = 32,
            patch_w: int = 32
    ) -> Union[np.ndarray, None]:
        patch_path = np.random.choice(self._patches_paths)
        patch_img = cv2.imread(patch_path)
        if patch_img is None:
            return None
        h, w, _ = patch_img.shape
        if h <= patch_h or w <= patch_w:
            patch = cv2.resize(patch_img, (patch_w, patch_h))
            return patch
        x1 = np.random.randint(0, w - patch_w + 1)
        y1 = np.random.randint(0, h - patch_h + 1)
        x2 = x1 + patch_w
        y2 = y1 + patch_h
        patch = patch_img[y1:y2, x1:x2, :]

        return patch

    @staticmethod
    def _random_patch_img_with_alpha(
            img: np.ndarray,
            patch: np.ndarray,
            alpha: float = 0.5
    ) -> Tuple[np.ndarray, List[int]]:
        """对patch根据alpha进行融合 后期可以考虑换分割或matting得到的mask/alpha matte"""
        h, w, c = img.shape
        patch_h, patch_w, _ = patch.shape
        patch_w = min(max(0., patch_w), w)
        patch_h = min(max(0., patch_h), h)
        x0 = np.random.randint(0, w - patch_w + 1)
        y0 = np.random.randint(0, h - patch_h + 1)
        x1, y1 = int(x0 + patch_w), int(y0 + patch_h)
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, w), min(y1, h)
        img_patch = img[y0:y1, x0:x1, :].copy()
        # 对patch 进行 alpha 融合
        fuse_patch = cv2.addWeighted(patch, alpha, img_patch, 1. - alpha, 0)
        img[y0:y1, x0:x1, :] = fuse_patch[:, :, :]
        patch_corner = [x0, y0, x1, y1]

        return img.astype(np.uint8), patch_corner


class LandmarksRandomBackgroundWithAlpha(LandmarksTransform):
    """Implement of Random-Patch data augment for performance improving
    of the occlusion object in landmarks-detection. 从随机选择的图片上
    随机crop一块, 对输入的人脸图片进行patch，模拟人脸被物体的遮挡."""

    def __init__(
            self,
            alpha: float = 0.3,
            prob: float = 0.5
    ):
        """random select a patch ratio.
        :param prob:
        :param alpha: max alpha value(<=0.5)
        """
        super(LandmarksRandomBackgroundWithAlpha, self).__init__()
        self._prob = prob
        self._alpha = alpha
        assert 0.1 < alpha <= 0.5
        self._background_paths = []
        self._background_root = Path(__file__).parent
        self._background_dirs = [
            os.path.join(self._background_root, "patches/hats"),  # 帽子
            os.path.join(self._background_root, "patches/clothes"),  # 衣服
            os.path.join(self._background_root, "patches/others")  # 其他背景
        ]
        self._init_background_paths()

    @autodtye_array
    def __call__(
            self,
            img: np.ndarray,
            landmarks: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:

        if np.random.uniform(0., 1.0) > self._prob:
            self.clear_affine()
            return img.astype(np.uint8), landmarks.astype(np.float32)

        w, h = img.shape[1], img.shape[0]  # original shape

        alpha = np.random.uniform(0.1, self._alpha)
        background = self._random_select_background(img_h=h, img_w=w)
        if background is None:
            self.flag = True
            return img.astype(np.uint8), landmarks.astype(np.float32)

        new_img = self._random_background_img_with_alpha(img=img, background=background, alpha=alpha)

        self.flag = True

        return new_img.astype(np.uint8), landmarks.astype(np.float32)

    def _init_background_paths(self):
        self._background_paths.clear()
        for d in self._background_dirs:
            files = [x for x in os.listdir(d) if
                     any((x.lower().endswith("jpeg"),
                          x.lower().endswith("jpg"),
                          x.lower().endswith("png")))]

            paths = [os.path.join(d, x) for x in files]
            self._background_paths.extend(paths)

    def _random_select_background(
            self,
            img_h: int = 128,
            img_w: int = 128
    ) -> Union[np.ndarray, None]:

        background_path = np.random.choice(self._background_paths)
        background_img = cv2.imread(background_path)
        if background_img is None:
            return None
        h, w, _ = background_img.shape
        if h <= img_h or w <= img_w:
            background = cv2.resize(background_img, (img_w, img_h))
            return background
        # 随机挑一个起点
        x1 = np.random.randint(0, w - img_w + 1)
        y1 = np.random.randint(0, h - img_h + 1)
        # 随机挑一个宽高
        nw = np.random.randint(img_w // 2, img_w)
        nh = np.random.randint(img_h // 2, img_h)
        x2 = x1 + nw
        y2 = y1 + nh
        background = background_img[y1:y2, x1:x2, :]

        # 确保和图片的大小一致
        if nh != img_h or nw != img_w:
            background = cv2.resize(background, (img_w, img_h))
            return background

        return background

    @staticmethod
    def _random_background_img_with_alpha(
            img: np.ndarray,
            background: np.ndarray,
            alpha: float = 0.5) -> np.ndarray:
        """对patch根据alpha进行融合 后期可以考虑换分割或matting得到的mask/alpha matte"""
        h, w, c = img.shape
        b_h, b_w, _ = background.shape
        if b_h != h or b_w != w:
            background = cv2.resize(background, (w, h))
        # 对背景 进行 alpha 融合
        img = cv2.addWeighted(background, alpha, img, 1. - alpha, 0)

        return img.astype(np.uint8)
