from scipy.spatial import distance as dist
from imutils import perspective
from imutils import contours
import numpy as np
import argparse
import imutils
import cv2
import time
from keras.models import model_from_json

json_file = open('model.json', 'r')
loaded_model_json = json_file.read()
model = model_from_json(loaded_model_json)
model.load_weights('model.h5')

width = 205
height = 215
center_x = np.float32(270)
center_y = np.float32(250)
roi_width = np.float32(370)
roi_height = np.float32(315)

def_rect = [(center_x, center_y), (roi_width, roi_height), 0.0]


def crop_pic(frame, center_x=center_x, center_y=center_y, roi_width=roi_width, roi_height=roi_height):
    # cv2.imshow("uncropped image", frame)
    orig = frame.copy()
    try:
        roi = frame[int(np.asscalar(center_y - roi_height / 2)): int(np.asscalar(center_y + roi_height / 2)),
                    int(np.asscalar(center_x - roi_width / 2)): int(np.asscalar(center_x + roi_width / 2))]
    except:
        roi = frame[int(center_y - roi_height / 2):int(center_y + roi_height / 2),
                    int(center_x - roi_width / 2):int(center_x + roi_width / 2)]
    return roi


def midpoint(ptA, ptB):
    return ((ptA[0] + ptB[0]) * 0.5, (ptA[1] + ptB[1]) * 0.5)


def crop_minAreaRect(img, rect):

    # rotate img
    angle = rect[2]
    rows, cols = img.shape[0], img.shape[1]
    M = cv2.getRotationMatrix2D((cols / 2, rows / 2), angle, 1)
    img_rot = cv2.warpAffine(img, M, (cols, rows))

    # rotate bounding box
    rect0 = (rect[0], rect[1], 0.0)
    box = cv2.boxPoints(rect)
    pts = np.int0(cv2.transform(np.array([box]), M))[0]
    pts[pts < 0] = 0

    # crop
    img_crop = img_rot[pts[1][1]:pts[0][1],
                       pts[1][0]:pts[2][0]]

    return img_crop


def find_box(contours, max_area, image):
    box_contour = contours[0]
    for c in contours:
        if cv2.contourArea(c) > cv2.contourArea(box_contour) and cv2.contourArea(c) < 45000:
            box_contour = c
            # print(cv2.contourArea(box_contour))
    box = cv2.minAreaRect(box_contour)
    min_rect = box
    straight_rect = cv2.boundingRect(box_contour)
    box_im = image[straight_rect[1]:straight_rect[1] + straight_rect[3],
                   straight_rect[0]: straight_rect[0] + straight_rect[2]]
    # print(box_im)
    try:
        cv2.imshow('box', box_im)
    except Exception:
        raise Exception
    box = cv2.cv.BoxPoints(
        box) if imutils.is_cv2() else cv2.boxPoints(box)
    box = np.array(box, dtype="int")
    box = perspective.order_points(box)
    cX = np.average(box[:, 0])
    cY = np.average(box[:, 1])
    (tl, tr, br, bl) = box
    (tlblX, tlblY) = midpoint(tl, bl)
    (trbrX, trbrY) = midpoint(tr, br)
    (tltrX, tltrY) = midpoint(tl, tr)
    (blbrX, blbrY) = midpoint(bl, br)
    D = dist.euclidean((tlblX, tlblY), (trbrX, trbrY))
    hoit = dist.euclidean((blbrX, blbrY), (tltrX, tltrY))
    refObj = (box, (cX, cY), D / width, box_contour, min_rect, hoit / height)
    bigbox = Box(contour=box_contour)
    ypixPerMet = hoit / height
    pixelsPerMetric = D / width
    return bigbox, pixelsPerMetric, ypixPerMet


def nothing(n):
    pass


def colourCheck(im, lowH, lowS, lowV, upH, upS, upV, threshblue):
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    # define range of blue color in HSV
    lower_blue = np.array([lowH, lowS, lowV])
    upper_blue = np.array([upH, upS, upV])

    # Threshold the HSV image to get only blue colors
    mask = cv2.inRange(hsv, lower_blue, upper_blue)

    # Bitwise-AND mask and original image
    res = cv2.bitwise_and(im, im, mask=mask)

    # check for blue from grayscale
    gray = cv2.cvtColor(res, cv2.COLOR_BGR2GRAY)

    # cv2.imshow('frame', im)
    # cv2.imshow('mask', mask)
    # cv2.imshow('bluecheck' + str(cX), res)
    # cv2.imshow('gray', gray)
    # bluecount = 0
    # for i in gray:
    #     for j in i:
    #         if j > 10:
    #             bluecount += 1
    bluecount = np.asscalar(np.sum(res))

    # print("blue: " + str(bluecount) + '<' + str(threshblue))
    # print(str(type(bluecount)) + "," + str(type(threshblue)))
    if bluecount >= threshblue:
        return True
    else:
        return False


def sizeCheck(im, lowH, lowS, lowV, upH, upS, upV, thresh, cX):
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    # define range of blue color in HSV
    # lower_color = np.array([110, 50, 50])
    # upper_color = np.array([130, 255, 255])
    lower_color = np.array([lowH, lowS, lowV])
    upper_color = np.array([upH, upS, upV])

    # Threshold the HSV image to get only blue colors
    mask = cv2.inRange(hsv, lower_color, upper_color)
    # Bitwise-AND mask and original image
    res = cv2.bitwise_and(im, im, mask=mask)
    # cv2.imshow('sizecheck' + str(cX), res)
    iteration = 0
    # for i in range(len(mask)):
    #     for j in range(len(mask[i])):
    #         if mask[i][j] > 0:
    #             iteration += 1
    iteration = np.asscalar(np.sum(res))
    print("size" + str(cX) + ":  " + str(iteration))
    if iteration > thresh:
        return True
    else:
        return False


def detect_type(orig, c, lowH, lowS, lowV, upH, upS, upV, thresh, lowblueH, lowblueS, lowblueV, upperblueH, upperblueS, upperblueV, bluethresh):
    # c = big_box[2]
    colors = ((0, 0, 255), (240, 0, 159), (0, 165, 255),
              (255, 255, 0), (255, 0, 255))
    cv2.drawContours(orig, c, 0, (0, 255, 0), 2)
    label = 'unknown'
    box = cv2.boundingRect(c)
    # contour_im = image[box[1]:box[1] +
    #                    box[3], box[0]:box[0] + box[2]]
    box = cv2.minAreaRect(c)
    contour_im = crop_minAreaRect(orig, box)
    # contour_im = image[int(box[0][1] - box[1][1] / 2):int(box[0][1] + box[1][1] / 2),
    #                    int(box[0][0] - box[1][0] / 2): int(box[0][0] + box[1][0] / 2)]
    min_rect = box
    box = cv2.cv.BoxPoints(
        box) if imutils.is_cv2() else cv2.boxPoints(box)
    box = np.array(box, dtype="int")
    box = perspective.order_points(box)
    cX = np.average(box[:, 0])
    cY = np.average(box[:, 1])
    try:
        colour = colourCheck(
            contour_im, lowblueH, lowblueS, lowblueV, upperblueH, upperblueS, upperblueV, bluethresh)
        size = sizeCheck(contour_im, lowH, lowS,
                         lowV, upH, upS, upV, thresh, cX)
        if colour == True:
            label = 'colored'
        elif size == True:
            label = 'small_pebbles'
        else:
            label = 'large_pebbles'
    except Exception:
        return None
    # cv2.imshow(label + str(int(cX)), contour_im)

    cv2.drawContours(orig, [box.astype("int")], -1, (0, 255, 0), 2)

    return label, min_rect


def drawBags(orig, box):
    # if big_box is not None:
    #     cv2.drawContours(
    #         orig, [big_box[0].astype("int")], -1, (0, 255, 0), 2)
    #     refCoords = np.vstack([big_box[0], big_box[1]])
    objCoords = np.vstack([box, (cX, cY)])
    for (x, y) in box:
        cv2.circle(orig, (int(x), int(y)), 5, (0, 0, 255), -1)
        (tl, tr, br, bl) = box
        cv2.putText(
            orig, label, (bl[0], bl[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
        (tltrX, tltrY) = midpoint(tl, tr)
        (blbrX, blbrY) = midpoint(bl, br)
        (tlblX, tlblY) = midpoint(tl, bl)
        (trbrX, trbrY) = midpoint(tr, br)
        dA = dist.euclidean((tltrX, tltrY), (blbrX, blbrY))
        dB = dist.euclidean((tlblX, tlblY), (trbrX, trbrY))

        dimA = dA / pixelsPerMetric
        dimB = dB / pixelsPerMetric

        # for ((xA, yA), (xB, yB), color) in zip(refCoords, objCoords, colors):
        #     cv2.circle(orig, (int(xA), int(yA)), 5, color, -1)
        #     cv2.circle(orig, (int(xB), int(yB)), 5, color, -1)
        # (xA, yA) = big_box[1]
        # (xB, yB) = (cX, cY)
        # color = (0, 255, 255)
        # cv2.line(orig, (int(xA), int(yA)),
        #          (int(xB), int(yB)), color, 2)
        # D = dist.euclidean((xA, yA), (xB, yB)) / big_box[2]
        # (mX, mY) = midpoint((xA, yA), (xB, yB))
        # cv2.putText(orig, "{:.1f}mm".format(D), (int(mX), int(mY - 10)),
        #             cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
        # cv2.putText(orig, "{:.1f}mm".format(dimA),
        #             (int(tltrX - 15), int(tltrY - 10)
        #              ), cv2.FONT_HERSHEY_SIMPLEX,
        #             0.65, (255, 255, 255), 2)
        # cv2.putText(orig, "{:.1f}mm".format(dimB),
        #             (int(trbrX + 10), int(trbrY)),
        #             cv2.FONT_HERSHEY_SIMPLEX,
        #             0.65, (255, 255, 255), 2)


g_kernel = 5
bi_kernel = 4
bi_area = 100
min_area = 1700
max_area = 17000
LOW_edge = 60
HIGH_edge = 120
current_filter = 2
lowH = 25
lowS = 6
lowV = 25
upH = 25
upS = 255
upV = 255
thresh = 42000
lowblueH = 110
lowblueS = 50
lowblueV = 50
upperblueH = 130
upperblueS = 255
upperblueV = 255
bluethresh = 10000


def get_contours(frame):

    gauss_args = [g_kernel, g_kernel]
    bilat_args = [bi_kernel, bi_area, bi_area]

    # cv2.imshow("uncropped image", frame)
    orig = frame.copy()

    image = orig

    edged = []
    # Apply filters

    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    except:
        gray = image

    # Contrast Limited Adaptive Histogram Equalization
    # clahe = cv2.createCLAHE()
    # cl1 = clahe.apply(gray)

    # gaussian blur
    # gauss = cv2.GaussianBlur(gray, (3, 3), 0)
    gauss = cv2.GaussianBlur(gray, (gauss_args[0], gauss_args[1]), 0)

    # global Histogram Equalization
    # global_histeq = cv2.equalizeHist(gray)

    # bilateralFilter
    bilat = cv2.bilateralFilter(
        gray, bilat_args[0], bilat_args[1], bilat_args[2])

    # total list of individual filters
    filtered = [gray, gray, gauss,
                bilat]

    # perform Canny edge detection on all filters
    for i in range(len(filtered)):
        edged.append(cv2.Canny(filtered[i], LOW_edge, HIGH_edge))
        edged[i] = cv2.dilate(edged[i], None, iterations=1)
        edged[i] = cv2.erode(edged[i], None, iterations=1)
        # cv2.imshow("dilated" + str(i) + str(num), edged[i])
    cv2.imshow("dilated" + str(current_filter), edged[current_filter])

    # findContours
    index = current_filter
    cnts = cv2.findContours(edged[index].copy(), cv2.RETR_EXTERNAL,
                            cv2.CHAIN_APPROX_SIMPLE)
    cnts = cnts[0] if imutils.is_cv2() else cnts[1]
    return cnts


def type_detect_trained(image, contour):
    cv2.drawContours(image, contour, 0, (0, 255, 0), 2)
    label = 'unknown'
    box = cv2.boundingRect(contour)
    # contour_im = image[box[1]:box[1] +
    #                    box[3], box[0]:box[0] + box[2]]
    box = cv2.minAreaRect(contour)
    # contour_im = crop_minAreaRect(image, box)
    if abs(box[2]) < 45:
        angle_of_rot = 0 - box[2]
    else:
        angle_of_rot = box[2] - 270
    rotated = imutils.rotate(image, angle=angle_of_rot)
    contour_im = crop_pic(rotated, box[0][0], box[0][1], 100, 100)
    # contour_im = image[int(box[0][1] - box[1][1] / 2):int(box[0][1] + box[1][1] / 2),
    #                    int(box[0][0] - box[1][0] / 2): int(box[0][0] + box[1][0] / 2)]
    min_rect = box
    box = cv2.cv.BoxPoints(
        box) if imutils.is_cv2() else cv2.boxPoints(box)
    box = np.array(box, dtype="int")
    box = perspective.order_points(box)
    cX = np.average(box[:, 0])
    cY = np.average(box[:, 1])
    cont_img = cv2.cvtColor(contour_im, cv2.COLOR_BGR2RGB)
    cont_img = np.array([cont_img.tolist()])
    prediction = model.predict(cont_img)
    print(prediction)
    prediction = prediction[0]
    if prediction[0] > prediction[1] and prediction[0] > prediction[2]:
        label = "colored"
    elif prediction[1] > prediction[0] and prediction[1] > prediction[2]:
        label = "large_pebbles"
    elif prediction[2] > prediction[0] and prediction[2] > prediction[1]:
        label = "small_pebbles"

    cv2.drawContours(image, [box.astype("int")], -1, (0, 255, 0), 2)

    return label, min_rect


def find_bags(cnts, image):
    if len(cnts) is not 0:
        # (cnts, _) = contours.sort_contours(cnts)
        orig = image.copy()
        big_box, pixelsPerMetric, ypixPerMet = find_box(cnts, 45000, image)

        bags = []
        for c in cnts:
            if cv2.contourArea(c) < min_area or cv2.contourArea(c) > max_area:
                continue

            try:
                type, min_rect = type_detect_trained(orig, c)
                # type, min_rect = detect_type(orig, c, lowH, lowS, lowV, upH, upS, upV, thresh, lowblueH,
                #                              lowblueS, lowblueV, upperblueH, upperblueS, upperblueV, bluethresh)
                bag = Bag(contour=c, type=type)
                cv2.putText(orig, bag.type, (int(bag.center[0]), int(
                    bag.center[1])), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
                bags.append(bag)
            except:
                pass
            # important!!!!
            # print(type)

        for bag in bags:
            print(str(bag))
        cv2.imshow("orig", orig)
        return bags, big_box, orig


def get_bags(frame, center_x=center_x, center_y=center_y, roi_width=roi_width, roi_height=roi_height):
    roi = crop_pic(frame, center_x, center_y, roi_width, roi_height)
    # bgsubbed = bgsub.apply(roi, learningRate=0)
    # contours = get_contours(bgsubbed)
    contours = get_contours(roi)
    for c in contours:
        cv2.drawContours(frame, c, 0, (0, 255, 0), 2)
    bags, box, orig = find_bags(contours, roi)
    return bags, box, orig


class Entity:
    """docstring for Entity."""

    def __init__(self, contour):
        super(Entity, self).__init__()
        self.contour = contour
        self.min_rect = cv2.minAreaRect(contour)
        self.center = self.min_rect[0]
        self.corners = cv2.boxPoints(self.min_rect)
        self.angle = self.min_rect[2]
        self.width = self.min_rect[1][0]
        self.height = self.min_rect[1][1]


class Box(Entity):
    """docstring for Box."""

    type = 'box'

    def __init__(self, type='box', **kwargs):
        super(Box, self).__init__(**kwargs)
        self.type = type

    def __str__(self):
        return "box"


class Bag(Entity):
    """docstring for Bag."""

    def __init__(self, type, **kwargs):
        super(Bag, self).__init__(**kwargs)
        self.type = type

    def __str__(self):
        return self.type + " at " + str(self.center[0]) + ", " + str(self.center[1])


period = 0.15
nexttime = time.time() + period

# try:
#     cap = cv2.VideoCapture(0)
# except:
#     cap = cv2.VideoCapture(1)
#
# # bgsub = cv2.bgsegm.createBackgroundSubtractorMOG()
# # ret, bg = cap.read()
# # bgsub.apply(bg, learningRate=0.5)
# # cv2.imshow("background", bg)
# ret, frame = cap.read()
# roi = crop_pic(frame, center_x, center_y, roi_width, roi_height)
# contours = get_contours(roi)
# box, x_pixels_per_mil, y_pixels_per_mil = find_box(contours, 45000, roi)
#
# Xbox, Ybox = box.center
# center_x = Xbox - x_pixels_per_mil * 50 + 270 - 185
# center_y = Ybox - y_pixels_per_mil * 50 + 250 - 157.5
# roi_width = x_pixels_per_mil * 400
# roi_height = y_pixels_per_mil * 400
#
# while(True):
#     ret, frame = cap.read()
#     if abs(box.min_rect[2]) < 45:
#         roteangle = 0 - box.min_rect[2]
#     else:
#         roteangle = box.min_rect[2] - 270
#     roted = imutils.rotate(frame, angle=roteangle)
#     cv2.imshow("rotated", roted)
#     # roted = bgsub.apply(roted, learningRate=0)
#     bags, new_box, orig = get_bags(
#         frame=roted, center_x=center_x, center_y=center_y, roi_width=roi_width, roi_height=roi_height)
#
#     if cv2.waitKey(1) & 0xFF == ord('q'):
#         break
