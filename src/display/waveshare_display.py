"""
Unified Waveshare e-paper display driver.

Supports:
  - 4-color displays (e.g. 10.85" G, SSD1681 dual-IC, 1360x480)
  - Bi-color displays (e.g. 7.5" HD V2, black + red)
  - Partial refresh (conservative 5:1 ratio with periodic full refresh)
  - 180-degree rotation patch for HAT orientation
  - Full-width rendering (width*2) for dual-IC panels

Author: allsafe-linux (Waveshare 10.85" G adaptation)
"""

import inspect
import importlib
import logging

# =============================================================================
# LAYER ARCHITECTURE:
# =============================================================================
# InkyPi uses a clean 4-layer separation for display support. This file is
# LAYER 2 (framework) and does NOT talk to hardware directly. Each layer has
# a distinct responsibility and changing one shouldn't require touching others.
#
#   LAYER 1 (business)    LAYER 2 (framework)        LAYER 3 (driver)
#   -----------------    ---------------------      -------------------
#   Plugins:             waveshare_display.py        epd10in85g.py
#   Clock/Weather/       - HAT rotation (180)       - SSD1681 commands
#   Meeting/etc.         - full-width (width * 2)   - dual-IC (CS_M + CS_S)
#   |                    - wake-up + Clear + sleep  - 4-color palette
#   v                    - abstract type routing    - 2-color split helper
#   display_image()      - 1 vs 2 buffer prep      - 4-color getbuffer
#
#   Knows about:         Knows about:                Knows about:
#   images, settings     refresh strategy,          SSD1681 chip, dual-IC
#                        display-type differences    commands, bit packing
#                        ------------------------
#                              | delegates to |
#                        LAYER 4 (hardware):
#                        epdconfig.py + DEV_Config_64_b.so
#                        - SPI write bytes, GPIO bits
#                        - bcm2835 C library
#
# NOTE: 4-color screens (e.g. 10.85" G) do NOT support partial refresh
# per Waveshare FAQ. Only B/W screens support it. This file always does
# full refresh, keeping things simple and compatible with all panel types.
#
# Naming convention:
#   * display_image()               - public entry point (called by Layer 1)
#   * _do_full_refresh()            - EXECUTION: Clear + display
#   * _prepare_display_layers()     - ABSTRACTION: 1 or 2 buffers depending on type
#   * _split_bi_color_layers()      - helper for 2-color displays only
# =============================================================================

import sys

from display.abstract_display import AbstractDisplay
from PIL import Image
from pathlib import Path

logger = logging.getLogger(__name__)


class WaveshareDisplay(AbstractDisplay):
    """
    Handles all Waveshare e-paper display types via a unified interface.

    Dynamically loads the driver module from `display.waveshare_epd.{display_type}`
    based on the `display_type` config field, then routes the image to the
    appropriate code path:
      - 4-color (1-arg display()): full-color image with internal palette quantization
      - Bi-color (2-arg display()): split into black + red 1-bit layers
    """

    # ----- Class constants -----
    HAT_ROTATION_DEG = 180             # HAT is mounted upside-down; rotate to fix
    DUAL_IC_WIDTH_MULTIPLIER = 2       # 10.85" G uses 2 SSD1681 ICs, each handles half width

    def initialize_display(self):
        """
        Dynamically load the Waveshare EPD driver module and initialize hardware.

        Raises:
            ValueError: If `display_type` is missing or driver is not found.
        """
        logger.info("Initializing Waveshare display")

        display_type = self.device_config.get_config("display_type")
        logger.info(f"Loading EPD display for {display_type} display")

        if not display_type:
            raise ValueError("Waveshare driver but 'display_type' not specified in configuration.")

        # Workaround: some Waveshare drivers do `import epdconfig` (relative-style),
        # which fails when loaded as a package. Add the driver dir to sys.path.
        epd_dir = Path(__file__).parent / "waveshare_epd"
        if str(epd_dir) not in sys.path:
            sys.path.insert(0, str(epd_dir))

        try:
            module_name = f"display.waveshare_epd.{display_type}"
            epd_module = importlib.import_module(module_name)
            self.epd_display = epd_module.EPD()
            # Some drivers use Init() (PascalCase), others use init(). Support both.
            self.epd_display_init = getattr(
                self.epd_display, "Init", getattr(self.epd_display, "init", None)
            )
            if not callable(self.epd_display_init):
                raise AttributeError("No Init/init method found")
            self.epd_display_init()

            # Detect bi-color by counting display() method arguments
            # 4-color: display(image)            → 1 arg
            # bi-color: display(black, red)      → 2 args
            display_args_spec = inspect.getfullargspec(self.epd_display.display)
            self.bi_color_display = len(display_args_spec.args) > 2
        except ModuleNotFoundError:
            raise ValueError(f"Unsupported Waveshare display type: {display_type}")
        except AttributeError:
            raise ValueError(f"Display does not support required methods: {display_type}")

        # Default resolution: for dual-IC displays (e.g. 10.85" G with 2x SSD1681),
        # the per-IC width is half the full width. InkyPi generates full-width images.
        if not self.device_config.get_config("resolution"):
            w = int(self.epd_display.width) * self.DUAL_IC_WIDTH_MULTIPLIER
            h = int(self.epd_display.height)
            self.device_config.update_value("resolution", [w, h], write=True)

    # ----- Display rendering -----

    def display_image(self, image, image_settings=[]):
        """
        Render an image to the Waveshare e-paper display.

        Pipeline:
          1. Apply HAT rotation patch (180 degrees)
          2. Compare with last image for partial-refresh opportunity
          3. Either skip (no change), partial-refresh, or full-refresh
          4. Sleep display to save power

        Args:
            image (PIL.Image): The image to display.
            image_settings (list, optional): Reserved for future per-plugin settings.
        """
        if not image:
            raise ValueError("No image provided.")

        # PATCH: rotate 180° to match HAT physical orientation
        image = image.rotate(self.HAT_ROTATION_DEG)

        logger.info("Displaying image to Waveshare display.")

        # Re-initialize (display wakes from sleep)
        self.epd_display_init()

        # Always full refresh (4-color screens do not support partial refresh per Waveshare FAQ)
        self._do_full_refresh(image)

        # Sleep to save power (e-paper holds image without power)
        logger.info("Putting Waveshare display into sleep mode for power saving.")
        self.epd_display.sleep()

    # ----- (2) Refresh strategy: decides WHICH mode -----

    def _do_full_refresh(self, image):
        """Clear + display the full image (uniform path for all display types)."""
        self.epd_display.Clear()
        layers = self._prepare_display_layers(image)
        self.epd_display.display(*layers)

    def _prepare_display_layers(self, image):
        """
        Prepare display buffers, abstracting away display-type differences.

        Returns a list of buffers to pass to the driver's display() method:
          - 4-color displays (e.g. 10.85" G): 1 buffer, driver does palette quantization
          - Bi-color displays (e.g. 7.5" HD V2): 2 buffers (black + red 1-bit layers)
          - 7-color displays (future): extend this method, no caller change needed

        The caller simply unpacks: self.epd_display.display(*layers).
        This unifies the 4-color and bi-color paths into a single uniform call site.
        """
        if self.bi_color_display:
            black_layer, red_layer = self._split_bi_color_layers(image)
            return [
                self.epd_display.getbuffer(black_layer),
                self.epd_display.getbuffer(red_layer),
            ]
        # 4-color path: single buffer, driver handles palette internally
        return [self.epd_display.getbuffer(image)]

    # ----- (4) Bi-color helper: only used by 2-color displays (only used by bi-color displays like 7.5" HD V2) -----

    @staticmethod
    def _split_bi_color_layers(image):
        """
        Convert an RGB image into two 1-bit layers for bi-color (black + red) e-paper.

        Returns:
            (black_layer, red_layer): Two PIL Image objects in mode '1' (1-bit)
        """
        black = (0, 0, 0)
        white = (255, 255, 255)
        red = (255, 0, 0)

        palette_data = [*black, *white, *red]
        palette_img = Image.new('P', (1, 1))
        palette_img.putpalette(palette_data)

        indexed_img = image.quantize(palette=palette_img, dither=Image.Dither.FLOYDSTEINBERG)
        black_layer = indexed_img.point(lambda p: 0 if p == 0 else 1, mode='1')
        red_layer = indexed_img.point(lambda p: 0 if p == 2 else 1, mode='1')
        return black_layer, red_layer