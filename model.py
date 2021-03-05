from dataclasses import dataclass


@dataclass
class Bus:
    busId: str
    lat: float
    lng: float
    route: str


@dataclass
class WindowBounds:
    north_lat: float = 0
    south_lat: float = 0
    east_lng: float = 0
    west_lng: float = 0

    def is_inside(self, lat, lng):
        if (self.north_lat > lat > self.south_lat) and (self.east_lng > lng > self.west_lng):
            return 1
        else:
            return 0

    def update(self, south_lat, north_lat, west_lng, east_lng):
        self.south_lat = south_lat
        self.north_lat = north_lat
        self.west_lng = west_lng
        self.east_lng = east_lng
