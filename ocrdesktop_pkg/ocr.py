"""OCR processing functionality using Tesseract."""

import re

import pytesseract
from pytesseract import Output
from PIL import Image, ImageOps


class OCRProcessor:
    """Handles OCR processing of images using Tesseract."""

    def __init__(self, language='eng', scale_factor=3, debug=False):
        self._language = language
        self._scale_factor = scale_factor
        self._debug = debug
        self._grayscale = False
        self._invert = False
        self._black_white = False
        self._black_white_value = 200

    @property
    def language(self):
        return self._language

    @language.setter
    def language(self, value):
        self._language = value

    @property
    def grayscale(self):
        return self._grayscale

    @grayscale.setter
    def grayscale(self, value):
        self._grayscale = value

    @property
    def invert(self):
        return self._invert

    @invert.setter
    def invert(self, value):
        self._invert = value

    @property
    def black_white(self):
        return self._black_white

    @black_white.setter
    def black_white(self, value):
        self._black_white = value

    @property
    def black_white_value(self):
        return self._black_white_value

    @black_white_value.setter
    def black_white_value(self, value):
        self._black_white_value = value

    def process_images(self, images, offset_x=0, offset_y=0, color_callback=None, include_word_list=True):
        """Process multiple images with OCR.

        Args:
            images: List of PIL Image objects
            offset_x: X offset for coordinate calculation
            offset_y: Y offset for coordinate calculation
            color_callback: Optional callback for color detection
            include_word_list: Whether to build detailed word list

        Returns:
            tuple: (ocr_text, word_list, modified_images)
        """
        if self._debug:
            print('start OCR')

        ocr_text = ''
        word_list = []
        modified_images = []

        for img in images:
            modified_img = self._transform_image(img)
            modified_images.append(modified_img)
            ocr_words = self._ocr_image(modified_img)
            text, words = self._process_ocr_words(
                ocr_words, modified_img, offset_x, offset_y,
                color_callback, include_word_list
            )
            ocr_text += text
            word_list.extend(words)

        if self._debug:
            print('OCR complete')

        ocr_text = self._clean_text(ocr_text)
        return ocr_text, word_list, modified_images

    def _transform_image(self, img):
        """Apply image transformations before OCR.

        Args:
            img: PIL Image

        Returns:
            PIL.Image: Transformed image
        """
        # Scale image
        width, height = img.size
        width *= self._scale_factor
        height *= self._scale_factor
        modified = img.resize((width, height), Image.Resampling.BICUBIC)

        if self._debug:
            modified.save("/tmp/ocrScreenshotScaled.png")
            print("save scaled screenshot:/tmp/ocrScreenshotScaled.png")

        # Apply transformations
        if self._invert:
            modified = ImageOps.invert(modified)
        if self._grayscale:
            modified = ImageOps.grayscale(modified)
        if self._black_white:
            lut = [255 if v > self._black_white_value else 0 for v in range(256)]
            modified = modified.point(lut)

        if self._debug:
            modified.save("/tmp/ocrScreenshotTransformed.png")
            print("save transformed screenshot:/tmp/ocrScreenshotTransformed.png")

        return modified

    def _ocr_image(self, img):
        """Run Tesseract OCR on image.

        Args:
            img: PIL Image

        Returns:
            dict: OCR results from pytesseract
        """
        if img is None:
            return {}
        return pytesseract.image_to_data(
            img,
            output_type=Output.DICT,
            lang=self._language,
            config='--psm 4'
        )

    def _process_ocr_words(self, ocr_words, img, offset_x, offset_y, color_callback, include_word_list):
        """Process OCR results into text and word list.

        Args:
            ocr_words: OCR results dictionary
            img: Source image for color detection
            offset_x: X offset for coordinates
            offset_y: Y offset for coordinates
            color_callback: Optional callback for color detection
            include_word_list: Whether to build word list

        Returns:
            tuple: (text, word_list)
        """
        text = ''
        word_list = []

        box_count = len(ocr_words.get('level', []))
        if box_count == 0:
            return text, word_list

        last_page = -1
        last_block = -1
        last_par = -1
        last_line = -1

        for i in range(box_count):
            word_text = ocr_words['text'][i]
            if not word_text or word_text.isspace():
                continue

            # Handle line breaks
            if last_line != -1:
                if (last_page != ocr_words['page_num'][i] or
                    last_block != ocr_words['block_num'][i] or
                    last_par != ocr_words['par_num'][i] or
                    last_line != ocr_words['line_num'][i]):
                    text += '\n'
                else:
                    text += ' '

            text += word_text

            # Build word list for GUI
            if include_word_list:
                color = 'unknown'
                if color_callback:
                    color = color_callback(ocr_words, i, img)

                x_pos = int(ocr_words['width'][i] / 2 + ocr_words['left'][i])
                y_pos = int(ocr_words['height'][i] / 2 + ocr_words['top'][i])

                word_list.append([
                    word_text,
                    round(ocr_words['height'][i] / 3 * 0.78, 0),  # Estimated font size
                    color,
                    'text',
                    x_pos,
                    y_pos,
                    int(float(ocr_words['conf'][i]))  # Confidence
                ])

            last_page = ocr_words['page_num'][i]
            last_block = ocr_words['block_num'][i]
            last_par = ocr_words['par_num'][i]
            last_line = ocr_words['line_num'][i]

        text += '\n'
        return text, word_list

    def _clean_text(self, text):
        """Clean up OCR text output.

        Args:
            text: Raw OCR text

        Returns:
            str: Cleaned text
        """
        # Remove double spaces
        text = re.compile(r'[^\S\r\n]{2,}').sub(' ', text)
        # Remove empty lines
        text = re.compile(r'\n\s*\n').sub('\n', text)
        # Remove ending spaces
        text = re.compile(r'\s*\n').sub('\n', text)
        # Remove trailing space in first line
        text = re.compile(r'^\s').sub('\n', text)
        # Remove ending newline
        text = re.compile(r'$\n').sub('', text)
        # Remove trailing spaces after newlines
        text = re.compile(r'\n\s').sub('\n', text)

        if text:
            text = text[:-1]
        return text
