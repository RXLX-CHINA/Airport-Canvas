"""Pushback line fillets and their tangent handles in world coordinates."""
import math

from curve_model import evaluate, node, rounded_nodes

DEFAULT_RADIUS = 5.0


def corner_handle(vertices, index, radius):
    previous, vertex, following = vertices[index-1:index+2]
    incoming = math.dist(previous, vertex)
    outgoing = math.dist(vertex, following)
    if min(incoming, outgoing) < .05:
        return None
    direction = [(a-b)/incoming for a,b in zip(previous, vertex)]
    dot = sum(u*(a-b)/outgoing for u,a,b in zip(direction, following, vertex))
    angle = math.acos(max(-1, min(1, -dot)))
    if not 1e-5 < angle <= math.radians(175):
        return None
    scale = math.tan(angle/2)
    limit = min(incoming, outgoing)*.49
    return direction, scale, limit, min(max(0, radius)*scale, limit)


def rounded_path(vertices, radii):
    if len(vertices) < 3:
        return vertices
    nodes = [node(vertices[0])]
    for index, vertex in enumerate(vertices[1:-1], 1):
        radius = max(0, radii.get(index, DEFAULT_RADIUS))
        if corner_handle(vertices, index, radius):
            arc, _ = rounded_nodes(vertices[index-1:index+2], radius)
            nodes.extend(arc[1:-1])
        else:
            nodes.append(node(vertex))
    nodes.append(node(vertices[-1]))
    try:
        return evaluate(nodes)
    except ValueError:
        return vertices


def relative_coordinates(scene, stand, points, *, restore=False, centreline=True):
    """Use the stand head as origin and the safety envelope as scale."""
    from stand13 import safety
    from stand11 import frame

    origin=stand['points'][-1]
    _,forward,lateral=frame(stand)

    def project(point, axis):
        return sum((p-o)*a for p,o,a in zip(point,origin,axis))

    boundary=safety(scene,stand)
    length=max(1.,max(abs(project(p,forward)) for p in boundary))
    if centreline:
        # The first stand point is its lead-in attachment on the centreline.
        reach=-project(stand['points'][0],forward)
        if reach>1e-6:
            length=reach
    width=max(1.,max(abs(project(p,lateral)) for p in boundary))
    if restore:
        return [[o+x*length*u+y*width*v for o,u,v in zip(origin,forward,lateral)]
                for x,y in points]
    return [[project(p,forward)/length,project(p,lateral)/width] for p in points]
