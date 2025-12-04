"""Color detection functionality for OCRdesktop."""

from collections import defaultdict

from .platform import scipy_available, webcolors_available, KDTree, CSS3_HEX_TO_NAMES, hex_to_rgb


class ColorDetector:
    """Detects and names colors in image regions."""

    def __init__(self, max_colors=3, debug=False):
        self._max_colors = max_colors
        self._debug = debug
        self._enabled = False
        self._kdt_db = None
        self._color_names = []
        self._color_cache = {}

    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, value):
        self._enabled = value

    @property
    def max_colors(self):
        return self._max_colors

    @max_colors.setter
    def max_colors(self, value):
        self._max_colors = value

    def get_color_string(self, box, index, img):
        """Get color string for a text box region.

        Args:
            box: OCR results dictionary with bounding box info
            index: Index of the word in the OCR results
            img: PIL Image to analyze

        Returns:
            str: Description of colors in the region
        """
        if not self._enabled:
            return 'unknown'

        if not scipy_available:
            if self._debug:
                print('getColorString scipy not available')
            return 'unknown'

        if not webcolors_available:
            if self._debug:
                print('getColorString webcolors not available')
            return 'unknown'

        if self._max_colors < 1:
            return 'unknown'

        if not img or not box:
            return 'unknown'

        try:
            width = box['width'][index]
            height = box['height'][index]
            left = box['left'][index]
            top = box['top'][index]

            box_img = img.crop((left, top, left + width, top + height))

            # Count colors
            by_color = defaultdict(int)
            for pixel in box_img.getdata():
                by_color[pixel] += 1

            # Convert to color names and count
            by_color_name = defaultdict(int)
            for color, count in by_color.items():
                by_color_name[self._rgb_to_name(color)] += count

            # Get top colors
            color_list = [k for k, v in sorted(by_color_name.items(), key=lambda item: item[1], reverse=True)]

            color_str = ''
            for i in range(min(self._max_colors, len(color_list))):
                color_name = color_list[i]
                count = by_color_name[color_name]
                if width * height != 0:
                    percent = int(round(count / (width * height) * 100, 0))
                    if percent > 0:
                        color_str += f'{color_name}: {percent} %, '
                else:
                    color_str += f'{color_name}: {count} pixel, '

            return color_str[:-2] if color_str else 'unknown'

        except Exception as e:
            if self._debug:
                print(f"Color detection error: {e}")
            return 'unknown'

    def _rgb_to_name(self, rgb_tuple):
        """Convert RGB tuple to nearest CSS color name.

        Args:
            rgb_tuple: (R, G, B) tuple

        Returns:
            str: CSS color name
        """
        # Check cache first
        if rgb_tuple in self._color_cache:
            return self._color_cache[rgb_tuple]

        # Build KDTree if not already done
        if self._kdt_db is None:
            css_db = CSS3_HEX_TO_NAMES
            rgb_values = []
            for color_hex, color_name in css_db.items():
                self._color_names.append(color_name)
                rgb_values.append(hex_to_rgb(color_hex))
            self._kdt_db = KDTree(rgb_values)

        # Find nearest color
        distance, index = self._kdt_db.query(rgb_tuple)
        result = self._color_names[index]
        self._color_cache[rgb_tuple] = result
        return result
