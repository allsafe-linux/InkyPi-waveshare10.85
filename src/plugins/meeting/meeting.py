from plugins.base_plugin.base_plugin import BasePlugin
import logging

logger = logging.getLogger(__name__)

MODE_PRESETS = {"nameplate": [{"id": "title_name", "label": "职务姓名（第一行）", "default_size": 110, "max_size": 180, "default_family": "ChineseDaHei", "default_weight": "bold", "default_color": "black", "default_align": "center"}, {"id": "company_org", "label": "单位公司（第二行）", "default_size": 65, "max_size": 110, "default_family": "ChineseKai", "default_weight": "normal", "default_color": "black", "default_align": "center"}, {"id": "contact", "label": "联系方式（第三行，可选）", "default_size": 32, "max_size": 55, "default_family": "ChineseFang", "default_weight": "normal", "default_color": "gray", "default_align": "center"}], "meeting": [{"id": "title", "label": "会议名称", "default_size": 100, "max_size": 140, "default_family": "ChineseKai", "default_weight": "bold", "default_color": "black", "default_align": "center"}, {"id": "time", "label": "时间", "default_size": 60, "max_size": 90, "default_family": "ChineseHei", "default_weight": "normal", "default_color": "black", "default_align": "center"}, {"id": "location", "label": "地点", "default_size": 48, "max_size": 75, "default_family": "ChineseHei", "default_weight": "normal", "default_color": "black", "default_align": "center"}, {"id": "host", "label": "主持人", "default_size": 40, "max_size": 60, "default_family": "ChineseFang", "default_weight": "normal", "default_color": "gray", "default_align": "center"}, {"id": "agenda", "label": "议程", "default_size": 36, "max_size": 52, "default_family": "ChineseFang", "default_weight": "normal", "default_color": "black", "default_align": "left"}, {"id": "notes", "label": "备注", "default_size": 30, "max_size": 44, "default_family": "ChineseFang", "default_weight": "normal", "default_color": "gray", "default_align": "left"}]}

FONT_FAMILIES = {"ChineseHei": "黑体 (simhei.ttf)", "ChineseKai": "楷体 (simkai.ttf)", "ChineseFang": "仿宋 (simfang.ttf)", "ChineseKaiGB": "楷体GB (楷体_GB2312.ttf)", "ChineseFangGB": "仿宋GB (仿宋_GB2312.ttf)", "ChineseDaHei": "大黑 (方正大黑_GBK.ttf)", "ChineseSong": "小标宋 (方正小标宋_GBK.ttf)", "ChineseWei": "魏碑 (方正魏碑_GBK.ttf)", "ChineseKaTong": "卡通 (方正卡通_GBK.ttf)"}
COLORS = {"black": "#000000", "white": "#ffffff", "red": "#c80000", "yellow": "#d4a000", "gray": "#666666"}
ALIGNMENTS = {"left": "左对齐", "right": "右对齐", "center": "居中对齐", "justify": "两端对齐", "justify-all": "分散对齐"}

class Meeting(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params["style_settings"] = True
        template_params["mode_presets"] = MODE_PRESETS
        template_params["font_families"] = FONT_FAMILIES
        template_params["colors"] = COLORS
        template_params["alignments"] = ALIGNMENTS
        return template_params

    def generate_image(self, settings, device_config):
        mode = settings.get("mode", "nameplate")
        preset = MODE_PRESETS.get(mode, MODE_PRESETS["nameplate"])

        fields = []
        for spec in preset:
            value = settings.get(f"field_{spec["id"]}", "").strip()
            fields.append({
                "id": spec["id"],
                "label": spec["label"],
                "value": value,
                "font_family": settings.get(f"font_{spec["id"]}", spec["default_family"]),
                "font_size": int(settings.get(f"size_{spec["id"]}", spec["default_size"])),
                "font_weight": settings.get(f"weight_{spec["id"]}", spec["default_weight"]),
                "color": settings.get(f"color_{spec["id"]}", spec["default_color"]),
                "align": settings.get(f"align_{spec["id"]}", spec["default_align"]),
            })

        active_fields = [f for f in fields if f["value"]]

        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        template_params = {
            "mode": mode,
            "fields": active_fields,
            "color_hex": COLORS,
            "plugin_settings": settings,
        }

        image = self.render_image(dimensions, "meeting.html", "meeting.css", template_params)
        return image
