# Create controller

import collections
import maya.cmds as cmds

TREE = lambda: collections.defaultdict(TREE)
INF_LINK = "ooc_controllers"
CTRL_LINK = "ooc_influence"

# Utility

def warning(text):
    """ Pop up a message """
    cmds.confirmDialog(t="Oh no!", m=text)

def ask(question):
    """ Ask user a question """
    return "Yes" == cmds.confirmDialog(t="Quick Question...", m=question, button=["Yes","No"], defaultButton="Yes", cancelButton="No", dismissString="No" )

def get_attr(node, attr, create=False):
    """ Get attribute. Creating one if it doesn't exist """
    if not cmds.attributeQuery(attr, n=node, ex=True) and create:
        cmds.addAttr(node, ln=attr, s=True)
    return node + "." + attr

def connections(*args, **kwargs):
    """ Grab connections """
    try:
        return cmds.listConnections(*args, **kwargs) or []
    except ValueError:
        return []

class Cache(object):
    """ Cached Functions """
    def __init__(s):
        s.skinCache = collections.defaultdict(list)
        s.geoCache = collections.defaultdict(list)
        s.infCache = collections.defaultdict(list)
        s.weightCache = TREE()

    def get_skins(s, joint):
        """ Yields skin names """
        if joint in s.skinCache:
            for skin in s.skinCache[joint]:
                yield skin
        else:
            for skin in set(connections(joint, s=False, type="skinCluster")):
                s.skinCache[joint].append(skin)
                yield skin

    def get_geos(s, skin):
        """ Yields geomrety names """
        if skin in s.geoCache:
            for geo in s.geoCache[skin]:
                yield geo
        else:
            for geo in cmds.skinCluster(skin, q=True, g=True) or []:
                s.geoCache[skin].append(geo)
                yield geo

    def get_influences(s, skin):
        """ Yields joints """
        if skin in s.infCache:
            for inf in s.infCache[skin]:
                yield inf
        else:
            for inf in cmds.skinCluster(skin, q=True, inf=True) or []:
                s.infCache[skin].append(inf)
                yield inf

    def get_weights(s, skin):
        """ Yields (vert ID, weights) """
        # Cache operation for multiple calls
        if skin not in s.weightCache:
            skin_attr = "%s.weightList" % skin
            for vert in cmds.getAttr(skin_attr, mi=True) or []:
                vert_attr = "%s[%s].weights" % (skin_attr, vert)
                weights = dict((a, cmds.getAttr("%s[%s]" % (vert_attr, a))) for a in cmds.getAttr(vert_attr, mi=True) or [])
                s.weightCache[skin][vert] = weights
        for vert, weights in s.weightCache[skin].iteritems():
            yield vert, weights

    def get_influence_include_exclude(s, joint):
        """ Get verts included and excluded from influence """
        geos = set()
        inclusion = collections.defaultdict(list)
        exclusion = collections.defaultdict(list)
        for skin in s.get_skins(joint):
            for geo in s.get_geos(skin):
                geos.add(geo)
                influences = list(s.get_influences(skin))
                if joint in influences:
                    inf_index = influences.index(joint)
                    for vert, weights in s.get_weights(skin):
                        for index in trim_weights(weights):
                            if inf_index == index:
                                inclusion[geo].append(vert)
                            else:
                                exclusion[geo].append(vert)
        return geos, inclusion, exclusion

def trim_weights(weights):
    """ Yields index(s) of winning weight(s) """
    highest = max(weights.values())
    for i, weight in weights.iteritems():
        if weight == highest: # Tie breaker, keep both!
            yield i

def convert_to_faces(selection):
    """ Turn a selection into a conservative face selection """
    return cmds.polyListComponentConversion(selection, tf=True, internal=True)

def create_shape(geo, xform):
    """ Create a Control that mimics the base geo """
    mesh = cmds.createNode("mesh", n="picker_%s" % xform, p=xform, ss=True)
    xform_compensate = cmds.createNode("transformGeometry", n="inverse_%s" % xform, ss=True)

    # Connect it all up!
    cmds.connectAttr("%s.worldInverseMatrix[0]" % xform, "%s.transform" % xform_compensate, f=True)
    cmds.connectAttr("%s.outMesh" % geo, "%s.inputGeometry" % xform_compensate)
    cmds.connectAttr("%s.outputGeometry" % xform_compensate, "%s.inMesh" % mesh)

    # Turn off rendering
    cmds.setAttr("%s.castsShadows" % mesh, 0)
    cmds.setAttr("%s.receiveShadows" % mesh, 0)
    cmds.setAttr("%s.motionBlur" % mesh, 0)
    cmds.setAttr("%s.primaryVisibility" % mesh, 0)
    cmds.setAttr("%s.smoothShading" % mesh, 0)
    cmds.setAttr("%s.visibleInReflections" % mesh, 0)
    cmds.setAttr("%s.visibleInRefractions" % mesh, 0)
    cmds.setAttr("%s.doubleSided" % mesh, 0)
    return mesh

def create_base(target, name):
    """ Create a base transform on the target """
    name = cmds.group(em=True, n=name)
    cmds.xform(name, ws=True, m=cmds.xform(target, q=True, ws=True, m=True))
    return name

def set_connected_controller(influence, controller):
    """ Forge a link to a controller """
    out_attr = get_attr(influence, INF_LINK, True)
    in_attr = get_attr(controller, CTRL_LINK, True)
    cmds.connectAttr(out_attr, in_attr)

def get_connected_controllers(influence):
    """ Get all linked controllers """
    attr = get_attr(influence, INF_LINK)
    return connections(attr, s=False)

def get_connected_influence(controller):
    """ Get all linked controllers """
    attr = get_attr(controller, CTRL_LINK)
    return connections(attr, d=False)

def create_invis_material():
    """ Make material to hide object """
    name = "invsible_material"
    if not cmds.objExists(name):
        name = cmds.shadingNode("surfaceShader", asShader=True, n=name)
        set_ = cmds.sets(r=True, nss=True, em=True, n="%sSG" % name)
        cmds.connectAttr("%s.outColor" % name, "%s.surfaceShader" % set_)
        cmds.setAttr("%s.outTransparency" % name, 1, 1, 1, type="double3")
    return name

def apply_material(obj, material):
    """ Apply material to an object """
    for set_ in connections("%s.outColor" % material):
        cmds.sets(obj, e=True, fe=set_)

def get_selected_joints():
    """ Get all joints in selection """
    return cmds.ls(sl=True, type="joint")

def update_controller(joint, cache):
    """ Update controllers given a joint """
    controllers = get_connected_controllers(joint)
    for controller in controllers:
        shapes = cmds.listRelatives(controller, c=True, s=True) # Grab old shapes
        cmds.delete(shapes) # Remove old shapes
        geos, include, exclude = cache.get_influence_include_exclude(joint) # find out what affects joint
        for geo in geos: # Run through meshes
            shape = create_shape(geo, controller) # Add mesh
            try:
                verts = ["%s.vtx[%s]" % (shape, a) for a in exclude[geo]]
                faces = convert_to_faces(verts)
                cmds.delete(faces)
            except ValueError: # Nothing to exclude? Moving on!
                pass

def build_controller(joint, cache):
    """ Create a new controller give a joint """
    geos, include, exclude = cache.get_influence_include_exclude(joint) # find out what affects joint
    if geos: # Check this joint actually has something to connect to
        material = create_invis_material()
        base = create_base(joint, "ctrl_%s" % joint) # make base to hold control mesh
        set_connected_controller(joint, base) # Link up control to joint
        apply_material(base, material) # Make invisible
        for geo in geos: # Run through meshes
            shape = create_shape(geo, base) # Add mesh
            try:
                verts = ["%s.vtx[%s]" % (shape, a) for a in exclude[geo]]
                faces = convert_to_faces(verts)
                cmds.delete(faces)
            except ValueError: # Nothing to exclude? Moving on!
                pass
        return base

def walk_children(obj):
    """ Walk down the hierarchy """
    children = cmds.listRelatives(obj, c=True) or []

class GUI(object):
    """ Main Window """
    def __init__(s):
        name = "controlwin"
        height = 30

        if cmds.window(name, q=True, ex=True):
            cmds.deleteUI(name)
        cmds.window(name, t="Contoller Setup", rtf=True)
        cmds.columnLayout(adj=True)

        s.create_from = cmds.optionMenu(h=height, l="Create from:", ann="""
Selected Joints: Use only joints selected. Useful if you have joints you wish to skip.
Joint Hierarchy: Use on selected joints and all decendants. Great for picking an entire skeleton from the root.
""")
        cmds.menuItem(l="Selected Joints")
        cmds.menuItem(l="Joint Hierarchy")

        s.create_type = cmds.radioCollection()
        cmds.radioButton(l="Loose Controls", ann="""
Create controls without any hierarchy.
Use this if you're going to set up the controls yourself.
""", sl=True)
        cmds.radioButton(l="Match Hierarchy", ann="""
Parent controls to one another to closely match the hierarchy of the picked skeleton.
Useful when doing a 1:1 skeleton controller setup.
""")
        cmds.radioButton(l="Force Single", ann="""
Create only a single control, incorporating all influence from selected joints.
Good for controls that will span multiple joints.
""")
        cmds.radioButton(l="Update Only", ann="""
Only update existing controls tied to the selected joints.
Use this when the rigs mesh or skinning has changed to reset control shapes to match.
""")

        s.constrain = cmds.checkBox(h=height, l="Constrain Joints", ann="""
Parent constrain the controls to the joints.
You can use this as a time saver for a quick and dirty setup.
""")

        cmds.button(h=height, l="Create", c=s.run)
        cmds.showWindow(name)

    def run(s, _):
        joints = set(cmds.ls(sl=True, type="joint"))
        if not joints: return warning("Please select some joints. :)")

        # Check if hierarchy is requested
        if 2 == cmds.optionMenu(s.create_from, q=True, sl=True):
            children = (cmds.listRelatives(a, ad=True, type="joint") or [] for a in joints)
            joints |= set(b for a in children for b in a)

        constrain = cmds.checkBox(s.constrain, q=True, v=True) # Do we constrain controllers?

        container = "controller_grp"
        if not cmds.objExists(container): # Build a container to hold our controllers
            cmds.group(em=True, n=container)

        btns = [a.split("|")[-1] for a in cmds.radioCollection(s.create_type, q=True, cia=True)]
        control_type = btns.index(cmds.radioCollection(s.create_type, q=True, sl=True))

        cache = Cache() # Speed up some function calls

        err = cmds.undoInfo(openChunk=True)
        cmds.select(cl=True)
        try:
            if control_type == 0:
                for jnt in joints:
                    control = build_controller(jnt, cache)
                    if control and constrain:
                        cmds.parentConstraint(control, jnt)
                print "Created controllers."
            if control_type == 1:
                print "hierarchy"
            if control_type == 2:
                print "TODO: Make this work!"
                return
                controllers = [build_controller(a, cache) for a in joints if a]
                base_ctrl = controllers[0]
                if 1 < len(controllers):
                    for control in controllers[1:]: # Pull out all shapes from controls and mush into one
                        for shape in cmds.listRelatives(control, c=True, s=True) or []:
                            print shape
                            cmds.parent(shape, base_ctrl, a=True, add=True, s=True)
                        cmds.delete(control) # Remove empty husk!
                cmds.parent(base_ctrl, container) # Keep organised!
                print "Created control %s." % base_ctrl
            if control_type == 3:
                for jnt in joints:
                    update_controller(jnt, cache)
                print "Controllers Updated."
        except Exception as err:
            raise
        finally:
            cmds.undoInfo(closeChunk=True)
            if err: cmds.undo()


def prep_test():
    cmds.file(new=True, force=True) # New blank scene for testing
    sphere = cmds.polySphere()[0] # Test Sphere
    jnt1, jnt2 = ((cmds.select(cl=True), cmds.joint(p=a))[1] for a in ((0,-1,0), (0,1,0))) # Add Joints
    skin = cmds.skinCluster(sphere, jnt1, jnt2)[0] # Add skin to sphere
    cmds.select(jnt1, jnt2, r=True)


if __name__ == '__main__':
    # prep_test()

    GUI()
