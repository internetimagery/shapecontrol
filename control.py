# Create controller

import collections
import maya.cmds as cmds

TREE = lambda: collections.defaultdict(TREE)
CTRL_LINK = "oocController"
INF_LINK = "oocInfluence"
PICKER_INF_LINK = "oocPickerInfluence"
PICKER_CTRL_LINK = "oocPickerController"


# Utility

def warning(text):
    """ Pop up a message """
    cmds.confirmDialog(t="Oh no!", m=text)

def ask(question):
    """ Ask user a question """
    return "Yes" == cmds.confirmDialog(t="Quick Question...", m=question, button=["Yes","No"], defaultButton="Yes", cancelButton="No", dismissString="No" )

def get_attr(node, attr, create=False):
    """ Get attribute. Creating one if it doesn't exist """
    if create:
        try:
            cmds.addAttr(node, ln=attr, s=True)
        except RuntimeError:
            pass
    return node + "." + attr

def connections(*args, **kwargs):
    """ Grab connections """
    try:
        return set(cmds.listConnections(*args, **kwargs) or [])
    except ValueError:
        return set()

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
            for skin in connections(joint, s=False, type="skinCluster"):
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
            influences = list(s.get_influences(skin))
            if joint in influences:
                inf_index = influences.index(joint)
                for vert, weights in s.get_weights(skin):
                    for index in trim_weights(weights):
                        for geo in s.get_geos(skin):
                            geos.add(geo)
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
    return cmds.polyListComponentConversion(selection, tf=True)
    # return cmds.polyListComponentConversion(selection, tf=True, internal=True)

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
    set_link(target, name, CTRL_LINK, INF_LINK)
    return name

def set_link(from_, to, out, in_):
    """ Forge a link """
    out_attr = get_attr(from_, out, True)
    in_attr = get_attr(to, in_, True)
    cmds.connectAttr(out_attr, in_attr, f=True)

def get_link(from_, link, **kwargs):
    """ Get linked objects """
    attr = get_attr(from_, link)
    return connections(attr, **kwargs)

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

def inject_shapes(influence, xform, geos, include, exclude, delete=True):
    """ Add shaped mesh to xform """
    material = create_invis_material()
    for geo in geos:
        shape = create_shape(geo, xform)
        apply_material(shape, material) # Make invisible
        set_link(influence, shape, PICKER_CTRL_LINK, PICKER_INF_LINK)
        if delete:
            try:
                verts = ["%s.vtx[%s]" % (shape, a) for a in exclude[geo]]
                faces = convert_to_faces(verts)
                cmds.delete(faces)
            except ValueError: # Nothing to exclude? Moving on!
                pass

def walk_up(obj):
    """ Walk up to root """
    parent = cmds.listRelatives(obj, p=True)
    if parent:
        parent = parent[0]
        yield parent
        for p in walk_up(parent):
            yield p

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

        cmds.separator()

        s.constrain = cmds.checkBox(l="Constrain Joints", ann="""
Parent constrain the controls to the joints.
You can use this as a time saver for a quick and dirty setup.
""")

        s.auto = cmds.checkBox(l="Automatic control shaping", ann="""
Shape the controls based on the joints influence.
The alternative is to manually go into each control and delete the faces you do not wish to be there.
Untick this only when getting undesired results from auto.
""", v=True)


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
        auto = cmds.checkBox(s.auto, q=True, v=True) # Do we automatically delete faces?

        container = "controller_grp"
        if not cmds.objExists(container): # Build a container to hold our controllers
            cmds.group(em=True, n=container)

        btns = [a.split("|")[-1] for a in cmds.radioCollection(s.create_type, q=True, cia=True)]
        control_type = btns.index(cmds.radioCollection(s.create_type, q=True, sl=True))

        cache = Cache() # Speed up some function calls

        err = cmds.undoInfo(openChunk=True)
        cmds.select(cl=True)
        new_controls = {}
        info = dict((a, cache.get_influence_include_exclude(a)) for a in joints)
        try:
            if control_type == 0: # loose control
                for jnt, inf in info.iteritems(): # Walk through info
                    geos, inc, exc = inf
                    if geos:
                        base = create_base(jnt, "%s_ctrl" % jnt)
                        cmds.parent(base, container)
                        new_controls[jnt] = base
                        inject_shapes(jnt, base, geos, inc, exc) # link up shape, autos
                print "Created controllers."
            if control_type == 1: # Match hierarchy
                bases = dict((a, create_base(a, "%s_ctrl" % a)) for a, b in info.iteritems() if b[0]) # Build out our bases
                for jnt, base in bases.iteritems():
                    geos, inc, exc = info[jnt]
                    new_controls[jnt] = base
                    for parent in walk_up(jnt): # Match Hierarchy.
                        if parent in bases:
                            cmds.parent(bases[jnt], bases[parent])
                            break
                    else:
                        cmds.parent(bases[jnt], container)
                    inject_shapes(jnt, base, geos, inc, exc, auto)
                print "Created controls, matching hierarchy."
            if control_type == 2: # Single control
                base = None
                for i, (jnt, inf) in enumerate(info.iteritems()):
                    geos, inc, exc = inf
                    if geos:
                        if not base:
                            base = create_base(jnt, "%s_ctrl" % jnt)
                            cmds.parent(base, container)
                            new_controls[jnt] = base
                        inject_shapes(jnt, base, geos, inc, exc, auto)
                if base:
                    print "Created control."
            if control_type == 3: # Update control
                for jnt in joints:
                    for control in get_link(jnt, CTRL_LINK, s=False, type="transform"): # get controllers
                        for shape in cmds.listRelatives(control, c=True, s=True) or []:
                            influences = get_link(shape, PICKER_INF_LINK, d=False, type="joint")
                            cmds.delete(shape)
                            for influence in influences:
                                if influence not in info:
                                    info[influence] = get_influence_include_exclude(influence)
                                geos, inc, exc = info[influence]
                                if geos:
                                    inject_shapes(influence, control, geos, inc, exc, auto)
                print "Controllers Updated."
            if new_controls:
                if constrain:
                    for jnt, control in new_controls.iteritems():
                        cmds.parentConstraint(control, jnt)
                cmds.select(new_controls.values(), r=True)
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
