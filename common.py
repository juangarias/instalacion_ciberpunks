import logging
import sys
import math
import os
from PIL import Image
import numpy as np
import cv2


def configureLogging(loglevel, logFile=None):
    numeric_level = getattr(logging, loglevel.upper(), None)

    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % loglevel)

    if logFile is not None:
        logging.basicConfig(level=numeric_level, filename=logFile,
                            format='%(levelname)s:%(funcName)s:%(message)s')
    else:
        logging.basicConfig(level=numeric_level, format='%(levelname)s:%(funcName)s:%(message)s')


def getFilename(filepath):
    (_, filenameExt) = os.path.split(filepath)
    filename, _ = os.path.splitext(filenameExt)
    return filename


def encodeSubjectPictureName(name, email):
    return name.replace(' ', '_') + '-' + email


def decodeSubjectPictureName(filename):
    if filename is None:
        return '', ''

    data = filename.split('-')
    name = data[0].replace('_', ' ')

    if len(data) > 1:
        email = data[1]
    else:
        email = ''

    return name, email


def loadCascadeClassifier(filename):
    logging.debug('Loading cascade classifier from {0}'.format(filename))
    cascade = cv2.CascadeClassifier(filename)
    if cascade.empty():
        raise ValueError('Cascade classifier is empty!')

    return cascade


def validImage(image):
    if image is None or len(image) == 0:
        return False

    (w, h) = image.shape[:2]

    return w > 0 and h > 0


def overlayImage(bg, fg, x, y):
    # Old version, doesnt take care of alpha channel.- jarias
    # back[y:y+fg.shape[0], x:x+fg.shape[1]] = fg

    for c in range(0, 3):
        bg[y:y+fg.shape[0], x:x+fg.shape[1], c] = fg[:,:,c] * (fg[:,:,3]/255.0) +  bg[y:y+fg.shape[0], x:x+fg.shape[1], c] * (1.0 - fg[:,:,3]/255.0)


def drawRectangle(image, square, color, thickness):
    (x, y, w, h) = square
    cv2.rectangle(image, (x, y), (x+w, y+h), color, thickness)


def drawLabel(text, image, position, fontFace=cv2.FONT_HERSHEY_SIMPLEX):
    scale = 0.6
    thickness = 1
    filledThickness = -1

    (x, y) = position
    ((textSizeX, textSizeY), _) = cv2.getTextSize(text, fontFace, scale, thickness)
    rectA = (x-5, y+5)
    rectB = (x+textSizeX+5, y-5-textSizeY)

    overlay = image.copy()
    cv2.rectangle(overlay, rectA, rectB, (0, 0, 0), filledThickness)
    cv2.putText(overlay, text, position, fontFace, scale, (255, 255, 255), thickness)

    opacity = 0.4
    cv2.addWeighted(overlay, opacity, image, 1 - opacity, 0, image)


def scaleCoords(square, image, outputWidth=None):
    if outputWidth is None:
        return square

    if image is None:
        raise ValueError("Image must be something")
    else:
        height, width = image.shape[:2]
        (outW, outH) = calculateScaledSize(outputWidth, image=image)
        (x, y, w, h) = square
        return (x * outW / width, y * outH / height, w * outW / width, h * outH / height)


def calculateScaledSize(outputWidth, image=None, capture=None):
    if image is not None:
        height, width = image.shape[:2]
    elif capture is not None:
        height = capture.get(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT)
        width = capture.get(cv2.cv.CV_CAP_PROP_FRAME_WIDTH)
    else:
        logging.error("Both arguments cannot be None.")
        raise ValueError("Image or capture must be something")

    proportionalHeight = int(outputWidth * height / width)
    return (outputWidth, proportionalHeight)


def resizeImage(image, size):
    # resize to given size (if given)
    if (size is None):
        return image
    else:
        return image.resize(size, Image.ANTIALIAS)


def readImages(paths, sz=None):
    images = []

    for path in paths:
        logging.debug('Reading files from {0}'.format(path))
        fileCount = 0
        totalFilesCount = sum([len(files) for r, d, files in os.walk(path)])
        print 'Reading directory {0}... '.format(path)
        for dirname, dirnames, filenames in os.walk(path):
            for filename in filenames:
                try:
                    im = cv2.imread(os.path.join(path, filename))
                    images.append(im)
                    fileCount += 1
                    sys.stdout.write("Loaded file {0} of {1}      \r".format(fileCount, totalFilesCount))
                    sys.stdout.flush()
                except IOError, (errno, strerror):
                    print "I/O error({0}): {1}".format(errno, strerror)
                except:
                    print "Unexpected error:", sys.exc_info()[0]
                    raise
        print('')

    return images


def readSubjectsImages(paths, sz=None):
    """Reads the images in a given folder, resizes images on the fly if size is given.

    Args:
        path: Path to a folder with subfolders representing the subjects (persons).
        sz: A tuple with the size Resizes

    Returns:
        A list [images,y]

            images: The images, which is a Python list of numpy arrays.
            labels: The corresponding labels (the unique number of the subject, person) in a Python list.
    """
    subjectId = 0
    images, labels, subjects = [], [], []
    for path in paths:
        logging.debug('Reading files from {0}'.format(path))
        fileCount = 0
        totalFilesCount = sum([len(files) for r, d, files in os.walk(path)])
        print 'Reading directory {0}... '.format(path)
        for dirname, dirnames, filenames in os.walk(path):
            for subdirname in dirnames:
                subject_path = os.path.join(dirname, subdirname)
                for filename in os.listdir(subject_path):
                    try:
                        im = cv2.imread(os.path.join(subject_path, filename))
                        images.append(im)
                        labels.append(subjectId)
                        fileCount += 1
                        sys.stdout.write("Loaded file {0} of {1}      \r".format(fileCount, totalFilesCount))
                        sys.stdout.flush()
                    except IOError, (errno, strerror):
                        print "I/O error({0}): {1}".format(errno, strerror)
                    except:
                        print "Unexpected error:", sys.exc_info()[0]
                        raise
                subjects.append(subdirname)
                subjectId += 1
        print('')

    return [images, np.asarray(labels, dtype=np.int32), subjects]


def shiftElementCoords(elements, offset):
    return [shiftCoords(x, offset) for x in elements]


def shiftCoords(square, offset):
    (xBase, yBase) = offset
    (x, y, h, w) = square

    return (xBase+x, yBase+y, h, w)


def detectFaces(image, faceCascade, leftEyeCascade, rightEyeCascade, minFaceSize=(100, 100), minEyeSize=(12, 18)):

    logging.debug("Detecting faces...")
    faceCandidates = detectElements(image, faceCascade, minFaceSize)
    faces = []

    for (x, y, w, h) in faceCandidates:
        logging.debug("Detected possible face: ({0},{1},{2},{3})".format(x, y, w, h))
        tempFace = image[y:y+h, x:x+w]
        faceUpper = tempFace[0:int(6*h/10), 0:w]

        leftEyesUpper = detectElements(faceUpper, leftEyeCascade, minEyeSize)
        rightEyesUpper = detectElements(faceUpper, rightEyeCascade, minEyeSize)

        if len(leftEyesUpper) <= 0 or len(rightEyesUpper) <= 0:
            continue

        leftEyes = shiftElementCoords(leftEyesUpper, (x, y))
        rightEyes = shiftElementCoords(rightEyesUpper, (x, y))

        logging.info("Detected face with {0} right eyes and {1} left eyes.".format(len(rightEyes), len(rightEyes)))

        faces.append((x, y, w, h, leftEyes, rightEyes))

    return faces


def detectElements(image, elementCascade, minSizeElem, recursiveSizeStep=0):
    haar_scale = 1.1
    min_neighbors = 5

    # Convert color input image to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Equalize the histogram
    gray = cv2.equalizeHist(gray)

    elements = elementCascade.detectMultiScale(gray, scaleFactor=haar_scale, minNeighbors=min_neighbors, minSize=minSizeElem)

    if (elements == () or len(elements) == 0):
        if recursiveSizeStep == 0:
            logging.debug("No elements found!")
            return []
        else:
            s1, s2 = minSizeElem
            logging.debug("No elements yet! Recursive call...")
            return detectElements(image, elementCascade, (s1 - recursiveSizeStep, s2 - recursiveSizeStep))
    else:
        logging.debug("Elements found:")
        logging.debug(elements)

        return elements


def calculateCenter(square):
    (a, b, w, h) = square
    wOffset = int(w/2)
    hOffset = int(h/2)
    return (a + wOffset, b + hOffset)


def Distance(p1, p2):
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    return math.sqrt(dx*dx+dy*dy)


def ScaleRotateTranslate(image, angle, center=None, new_center=None, scale=None, resample=Image.BICUBIC):
    if (scale is None) and (center is None):
        return image.rotate(angle=angle, resample=resample)
    nx, ny = x, y = center
    sx = sy = 1.0
    if new_center:
        (nx, ny) = new_center
    if scale:
        (sx, sy) = (scale, scale)
    cosine = math.cos(angle)
    sine = math.sin(angle)
    a = cosine/sx
    b = sine/sx
    c = x-nx*a-ny*b
    d = -sine/sy
    e = cosine/sy
    f = y-nx*d-ny*e
    return image.transform(image.size, Image.AFFINE, (a, b, c, d, e, f), resample=resample)


def cropFace(image, eye_left, eye_right, offset_pct=(0.3, 0.3), dest_sz=(92, 112)):
    image = Image.fromarray(np.uint8(image))
    # calculate offsets in original image
    offset_h = math.floor(float(offset_pct[0])*dest_sz[0])
    offset_v = math.floor(float(offset_pct[1])*dest_sz[1])
    # get the direction
    eye_direction = (eye_right[0] - eye_left[0], eye_right[1] - eye_left[1])
    # calc rotation angle in radians
    rotation = -math.atan2(float(eye_direction[1]), float(eye_direction[0]))
    # distance between them
    dist = Distance(eye_left, eye_right)
    # calculate the reference eye-width
    reference = dest_sz[0] - 2.0*offset_h
    # scale factor
    scale = float(dist)/float(reference)
    logging.debug("Scale and rotating to center: {0} and angle: {1}".format(eye_left, rotation))
    # rotate original around the left eye
    image = ScaleRotateTranslate(image, center=eye_left, angle=rotation)
    # crop the rotated image
    crop_xy = (eye_left[0] - scale*offset_h, eye_left[1] - scale*offset_v)
    crop_size = (dest_sz[0]*scale, dest_sz[1]*scale)
    image = image.crop((int(crop_xy[0]), int(crop_xy[1]), int(crop_xy[0]+crop_size[0]), int(crop_xy[1]+crop_size[1])))
    # resize it
    image = image.resize(dest_sz, Image.ANTIALIAS)
    return np.array(image)
