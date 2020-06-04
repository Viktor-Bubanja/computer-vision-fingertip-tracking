import cv2
import numpy as np
import math

DEFECT_THRESHOLD = 12000
THUMB_THRESHOLD = 100
MIN_CONTOUR_AREA = 20000
hand_hist = None
total_rectangle = 9
hand_rect_one_x = None
hand_rect_one_y = None

hand_rect_two_x = None
hand_rect_two_y = None

finger_path = []
convex_defects = []


def draw_lines(width, height, frame):
    x1, x2, = 0, int(width)
    line_thickness = 2
    step_size = int(2 * height / (3 * 4))
    for y in range(0, int((2 * height / 3) + step_size), step_size):
        cv2.line(frame, (x1, int(y)), (x2, int(y)), (0, 255, 0), line_thickness)


def rescale_frame(frame, wpercent=130, hpercent=130):
    width = int(frame.shape[1] * wpercent / 100)
    height = int(frame.shape[0] * hpercent / 100)
    return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)


def contours(hist_mask_image):
    gray_hist_mask_image = cv2.cvtColor(hist_mask_image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray_hist_mask_image, 0, 255, cv2.THRESH_BINARY)
    cont, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    return cont


"""
Draw rectangles on the frame to indicate to the user where they should place their hand.
The colours of the pixels within the rectangles are later extracted to generate a histogram.
"""
def draw_hist_rectangles(frame):
    rows, cols, _ = frame.shape
    global total_rectangle, hand_rect_one_x, hand_rect_one_y, hand_rect_two_x, hand_rect_two_y

    hand_rect_one_x = np.array(
        [6 * rows / 20, 6 * rows / 20, 6 * rows / 20, 9 * rows / 20, 9 * rows / 20, 9 * rows / 20, 12 * rows / 20,
         12 * rows / 20, 12 * rows / 20], dtype=np.uint32)

    hand_rect_one_y = np.array(
        [9 * cols / 20, 10 * cols / 20, 11 * cols / 20, 9 * cols / 20, 10 * cols / 20, 11 * cols / 20, 9 * cols / 20,
         10 * cols / 20, 11 * cols / 20], dtype=np.uint32)

    hand_rect_two_x = hand_rect_one_x + 10
    hand_rect_two_y = hand_rect_one_y + 10

    for i in range(total_rectangle):
        cv2.rectangle(frame, (hand_rect_one_y[i], hand_rect_one_x[i]),
                      (hand_rect_two_y[i], hand_rect_two_x[i]),
                      (0, 255, 0), 1)

    return frame


"""
Extract pixels within rectangles and generate HSV histogram.
"""
def hand_histogram(frame):
    global hand_rect_one_x, hand_rect_one_y

    hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    roi = np.zeros([90, 10, 3], dtype=hsv_frame.dtype)

    for i in range(total_rectangle):
        roi[i * 10: i * 10 + 10, 0: 10] = hsv_frame[hand_rect_one_x[i]:hand_rect_one_x[i] + 10,
                                          hand_rect_one_y[i]:hand_rect_one_y[i] + 10]

    hand_hist = cv2.calcHist([roi], [0, 1], None, [180, 256], [0, 180, 0, 256])
    return cv2.normalize(hand_hist, hand_hist, 0, 255, cv2.NORM_MINMAX)


"""
Given a frame and a histogram, finds all regions that match the histogram using Histogram Back Projection.
Returns a frame containing only these features.
"""
def hist_masking(frame, hist):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    dst = cv2.calcBackProject([hsv], [0, 1], hist, [0, 180, 0, 256], 1)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
    cv2.filter2D(dst, -1, kernel, dst)

    hist_threshold_min = 130
    hist_threshold_max = 255
    _, thresh = cv2.threshold(dst, hist_threshold_min, hist_threshold_max, cv2.THRESH_BINARY)
    thresh = cv2.merge((thresh, thresh, thresh))

    hist_mask_image = cv2.dilate(thresh, None, iterations=2)
    hist_mask_image = cv2.erode(hist_mask_image, None, iterations=2)

    return cv2.bitwise_and(frame, hist_mask_image)


# Terrible hist masking method. Use in report for bad example
def hist_masking2(frame, hist):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    dst = cv2.calcBackProject([hsv], [0,1], hist, [0,180,0,256], 1)

    disc = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11,11))
    cv2.filter2D(dst, -1, disc, dst)

    _, thresh = cv2.threshold(dst, 100, 255, 0)
    thresh = cv2.merge((thresh,thresh, thresh))

    cv2.GaussianBlur(dst, (3,3), 0, dst)

    res = cv2.bitwise_and(frame, thresh)
    return res


def find_centroid(max_contour):
    moment = cv2.moments(max_contour)
    cx = int(moment['m10'] / moment['m00'])
    cy = int(moment['m01'] / moment['m00'])
    return cx, cy


def draw_circles(frame, point_path):
    last_point = point_path[-1]
    for i in range(len(point_path) - 1):
        cv2.circle(frame, point_path[i], int(5 - (5 * i * 3) / 100), [0, 255, 255], -1)
    cv2.circle(frame, last_point, 5, [0, 0, 255], -1)



def find_fingertip(frame, hist_mask_image):
    global finger_path
    global convex_defects
    convex_defects.clear()
    contour_list = contours(hist_mask_image)
    print(len(contour_list))
    if contour_list:
        # Only identifying significant contours before finding contour with maximum area
        contour_list = list(filter(lambda x: cv2.contourArea(x) > MIN_CONTOUR_AREA, contour_list))
        if not contour_list:
            return None
        max_cont = max(contour_list, key=cv2.contourArea)
        centroid = find_centroid(max_cont)
        cv2.circle(hist_mask_image, centroid, 3, [20, 160, 50], -1)
        drawable_hull = cv2.convexHull(max_cont)
        cv2.drawContours(hist_mask_image, [drawable_hull], -1, (255, 0, 0), 2)
        formatted = [tuple(i[0]) for i in drawable_hull]
        fused_hull = sorted(fuse(formatted, 30), key=lambda point: point[1])

        hull = cv2.convexHull(max_cont, returnPoints=False)
        defects = cv2.convexityDefects(max_cont, hull)
        for i in range(defects.shape[0]):
            s, e, f, d = defects[i, 0]
            far = tuple(max_cont[f][0])
            if d > DEFECT_THRESHOLD and far[1] < centroid[1] + THUMB_THRESHOLD:
                convex_defects.append(far)
                cv2.circle(hist_mask_image, far, 5, [255, 255, 255], -1)

        for i in range(len(convex_defects) + 1):
            point = (int(fused_hull[i][0]), int(fused_hull[i][1]))
            print(point)
            cv2.circle(hist_mask_image, point, 10, [0, 0, 255], -1)


        if len(contour_list) > 1:
            second_max = contour_list[-2]
            top2 = tuple(second_max[second_max[:, :, 1].argmin()][0])
            cv2.circle(hist_mask_image, top2, 5, [90, 255, 90], -1)
            drawable_hull = cv2.convexHull(second_max)
            cv2.drawContours(hist_mask_image, [drawable_hull], -1, (255, 0, 0), 2)


        return None
    else:
        return None


def dist2(p1, p2):
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

def fuse(points, distance):
    ret = []
    n = len(points)
    taken = [False] * n
    for i in range(n):
        if not taken[i]:
            count = 1
            point = [points[i][0], points[i][1]]
            taken[i] = True
            for j in range(i+1, n):
                if dist2(points[i], points[j]) < distance:
                    point[0] += points[j][0]
                    point[1] += points[j][1]
                    count+=1
                    taken[j] = True
            point[0] /= count
            point[1] /= count
            ret.append((point[0], point[1]))
    return ret



def main():
    global hand_hist
    cap = cv2.VideoCapture(0)

    frame = None

    while cv2.waitKey(1) & 0xFF != ord('z'):
        _, frame = cap.read()
        frame = cv2.flip(frame, 1)
        draw_hist_rectangles(frame)
        cv2.imshow("Live Feed", rescale_frame(frame))

    hand_hist = hand_histogram(frame)

    while cv2.waitKey(1) & 0xFF != ord('q'):
        _, frame = cap.read()
        frame = cv2.flip(frame, 1)

        hist_mask_image = hist_masking(frame, hand_hist)

        far_point = find_fingertip(frame, hist_mask_image)
        if far_point:
            finger_path.append(far_point)
            if len(finger_path) > 20:
                finger_path.pop(0)

            draw_circles(frame, finger_path)
        cv2.imshow("Live Feed", rescale_frame(hist_mask_image))

    cv2.destroyAllWindows()
    cap.release()


if __name__ == '__main__':
    main()