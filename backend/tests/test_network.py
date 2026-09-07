from app.network import RoadNetwork, haversine


def test_haversine_positive():
    assert haversine((0, 0), (0, 0.01)) > 0


def test_shortest_path():
    routes = [{
        "id_trm_cs": 1,
        "nombre_tramo": "x",
        "color": "#000",
        "points": [[0, 0], [0, 0.01], [0, 0.02]],
    }]
    net = RoadNetwork(routes)
    result = net.shortest_path((0, 0), (0, 0.02))
    assert result is not None
    path, distance = result
    assert len(path) == 3
    assert distance > 0
