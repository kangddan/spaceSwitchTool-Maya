import maya.cmds         as cmds
import maya.api.OpenMaya as om2
import PySide2.QtWidgets as QtWidgets
import PySide2.QtCore    as QtCore
import PySide2.QtGui     as QtGui

def mayaMainWindow():
    import sys
    from maya.OpenMayaUI import MQtUtil
    from shiboken2       import wrapInstance
    if sys.version_info.major >= 3:
        return wrapInstance(int(MQtUtil.mainWindow()), QtWidgets.QMainWindow)
    else:
        return wrapInstance(long(MQtUtil.mainWindow()), QtWidgets.QMainWindow)
        
def uniqueName(name):
    startNum = 0; newName = name
    while cmds.objExists(newName):
        startNum += 1
        newName = '{}_{:03d}'.format(name, startNum)
    return newName
    
def getSelection():
    sel = om2.MGlobal.getActiveSelectionList()
    for i in range(sel.length()):
        mobj = sel.getDependNode(i)
        yield sel.getDagPath(i) if mobj.hasFn(om2.MFn.kDagNode) else om2.MFnDependencyNode(mobj)
        
# ------------------------------------------       
class MetaNode(object):
    CACHE = {}
    
    def __init__(self, nodeName):
        self.apiObject = nodeName
        
    @property
    def apiObject(self):
        return self._node
    
    @apiObject.setter
    def apiObject(self, nodeName):
        mobj = om2.MGlobal.getSelectionListByName(nodeName).getDependNode(0)
        self._node = om2.MFnDependencyNode(mobj)
        
    @property
    def name(self):
        return self.apiObject.name()
        
    
    
    
    
    @property
    def uuid(self):
        return self.apiObject.uuid().asString()
        

node = MetaNode('upr_ctrla_spaceSwitch_meta')
node.uuid
        
        
class MetaUtils(object):
    _NODETYPE_   = 'network'
    _META_VALUE_ = 'spaceSwitch'
    
    @classmethod
    def getMetaNodes(cls):
        return [node for node in cmds.ls(typ=cls._NODETYPE_)
                if cmds.attributeQuery('metaType', n=node, ex=True) and 
                cmds.getAttr('{}.metaType'.format(node)) == cls._META_VALUE_]
        
    @classmethod
    def createMetaNode(cls, ctrlName):
        metaNode = cmds.createNode(cls._NODETYPE_, name='{0}_spaceSwitch_meta'.format(ctrlName))
        # ----------------------------------------------------
        cmds.addAttr(metaNode, ln='metaType', dt='string')
        cmds.setAttr('{}.metaType'.format(metaNode), cls._META_VALUE_, typ='string')
        cmds.setAttr('{}.metaType'.format(metaNode), lock=True)
        cmds.addAttr(metaNode, ln='source', at='message')
        cmds.addAttr(metaNode, ln='offsetGroup', at='message')
        cmds.addAttr(metaNode, ln='constraints', nc=4, at='compound')
        cmds.addAttr(metaNode, ln='positionConstraint', at='message', p='constraints')
        cmds.addAttr(metaNode, ln='rotationConstraint', at='message', p='constraints')
        cmds.addAttr(metaNode, ln='scaleConstraint',    at='message', p='constraints')
        cmds.addAttr(metaNode, ln='parentConstraint',   at='message', p='constraints')
        
        # ----------------------------------------------------
        cmds.addAttr(metaNode, ln='target', nc=6, at='compound', m=True)
        cmds.addAttr(metaNode, ln='enumAttrName', dt='string', p='target')
        cmds.addAttr(metaNode, ln='spaceSwitchLocator', at='message', p='target')
        cmds.addAttr(metaNode, ln='p', at='bool',                    p='target')
        cmds.addAttr(metaNode, ln='s', at='bool',                    p='target')
        cmds.addAttr(metaNode, ln='r', at='bool',                    p='target')
        cmds.addAttr(metaNode, ln='depNodes', at='message', m=True,  p='target')
        #cmds.addAttr(metaNode, ln='depNodes',   dt='string', m=True, p='target')
        #cmds.addAttr(metaNode, ln='depNodes', dt='string', m=True, p='target')
        #cmds.addAttr(metaNode, ln='depNodes2', dt='string', p='target')

        
MetaUtils.createMetaNode('upr_ctrla')   
#MetaUtils.getMetaNodes()   
# ------------------------------------------         
'''
class SpaceSwitchUI(QtWidgets.QDialog):
    INSTANCE = None
    
    def showEvent(self, event):
        if self.geometry:
            self.restoreGeometry(self.geometry)
        super(SpaceSwitchUI, self).showEvent(event)
            
    def closeEvent(self, event):
        super(SpaceSwitchUI, self).closeEvent(event)
        self.geometry = self.saveGeometry()
        
    @classmethod
    def displayUI(cls):
        if cls.INSTANCE is None:
            cls.INSTANCE = SpaceSwitchUI()
  
        if cls.INSTANCE.isHidden():
            cls.INSTANCE.show()
            
        else:
            if cls.INSTANCE.isMinimized():
                cls.INSTANCE.showNormal()
            cls.INSTANCE.raise_()
            cls.INSTANCE.activateWindow()
            
    def __init__(self, parent=mayaMainWindow()):
        super(SpaceSwitchUI, self).__init__(parent)
        self.geometry = None
        self.setWindowFlags(QtCore.Qt.WindowType.Window)
        self.resize(300, 400)
        
if __name__ == '__main__':
    SpaceSwitchUI.displayUI()
'''


            
