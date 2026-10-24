from msgspec import Struct, field


class AnchorInfo(Struct):
    name: str = ""
    face: str = ""


class RoomData(Struct):
    """room/v1/Room/get_info 返回的直播间信息。"""

    uid: int
    raw_title: str = field(name="title")
    cover: str = field(default="", name="user_cover")
    keyframe: str = ""
    tags: str = ""
    area_name: str = ""
    parent_area_name: str = ""

    @property
    def title(self) -> str:
        return f"直播 - {self.raw_title}"

    @property
    def detail(self) -> str:
        return f"分区: {self.area_name} | {self.parent_area_name}\n标签: {self.tags}"
