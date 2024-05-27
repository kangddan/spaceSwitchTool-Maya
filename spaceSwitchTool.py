import maya.cmds         as cmds
import maya.api.OpenMaya as om2
import PySide2.QtWidgets as QtWidgets
import PySide2.QtCore    as QtCore
import PySide2.QtGui     as QtGui
from functools import partial

def addUndo(func):
    def undo(*args, **kwargs):
        cmds.undoInfo(openChunk=True)
        func(*args, **kwargs)
        cmds.undoInfo(closeChunk=True)
    return undo      

def mayaMainWindow():
    import sys
    from maya.OpenMayaUI import MQtUtil
    from shiboken2       import wrapInstance
    if sys.version_info.major >= 3:
        return wrapInstance(int(MQtUtil.mainWindow()), QtWidgets.QMainWindow)
    else:
        return wrapInstance(long(MQtUtil.mainWindow()), QtWidgets.QMainWindow)
        
def getSelection():
    sel = om2.MGlobal.getActiveSelectionList()
    return [sel.getDagPath(i) 
            if sel.getDependNode(i).hasFn(om2.MFn.kDagNode) 
            else om2.MFnDependencyNode(sel.getDependNode(i)) 
            for i in range(sel.length())]
            
def getNodeLongName(obj):
    '''
    return: name, longName
    '''
    if isinstance(obj, om2.MFnDependencyNode):
        return obj.name(), obj.name()
    else:
        return obj.fullPathName().split('|')[-1], obj.fullPathName()

        
class MetaUtils(object):
    
    @staticmethod
    def createMetaNode(nodeName, nodeType):
        metaNode = cmds.createNode(nodeType, name=nodeName.format(nodeName))
        # ----------------------------------------------------
        cmds.addAttr(metaNode, ln='metaClass', dt='string')
        cmds.setAttr('{}.metaClass'.format(metaNode), 'SpaceSwitch', typ='string')
        cmds.setAttr('{}.metaClass'.format(metaNode), lock=True)
        cmds.addAttr(metaNode, ln='source', at='message')
        cmds.addAttr(metaNode, ln='offsetGroup', at='message')
        cmds.addAttr(metaNode, ln='constraints', nc=4, at='compound')
        cmds.addAttr(metaNode, ln='pointConstraint', at='message', p='constraints')
        cmds.addAttr(metaNode, ln='orientConstraint',at='message', p='constraints')
        cmds.addAttr(metaNode, ln='scaleConstraint', at='message', p='constraints')
        cmds.addAttr(metaNode, ln='parentConstraint',at='message', p='constraints')
        
        # ----------------------------------------------------
        cmds.addAttr(metaNode, ln='target', nc=2, at='compound', m=True)
        cmds.addAttr(metaNode, ln='attrName', dt='string', p='target')
        cmds.addAttr(metaNode, ln='spaceTarget', at='message', p='target')
        # ----------------------------------------------------
        cmds.addAttr(metaNode, ln='spaceLocs', dt='string', m=True)
        cmds.addAttr(metaNode, ln='conditionNodes', dt='string', m=True)
        cmds.addAttr(metaNode, ln='offsetGroupLocalMatrix', dt="matrix")
        return metaNode
    
    @staticmethod
    def connectMiAttr(node, attr, metaNode, metaAttr):
        index = 0  
        while True:
            fullPathAttr = '{}.{}[{}]'.format(metaNode, metaAttr, index)
            if cmds.listConnections(fullPathAttr, d=False) is None:
                cmds.connectAttr('{}.{}'.format(node, attr), fullPathAttr, f=True)
                break   
            index += 1 
    
    @staticmethod
    def isUuidValid(uuid):
        if isinstance(uuid, str):
            return om2.MUuid(uuid).valid()
        elif isinstance(uuid, om2.MUuid):
            return uuid.valid()
        return False
        
    @staticmethod
    def getMetaNodes():
        return [SpaceSwitchMeta(node) for node in cmds.ls(typ='network')
                if cmds.attributeQuery('metaClass', n=node, ex=True) and 
                cmds.getAttr('{}.metaClass'.format(node)) == 'SpaceSwitch']
                
    @staticmethod            
    def uniqueName(name):
        startNum = 0; newName = name
        while cmds.objExists(newName):
            startNum += 1
            newName = '{}_{:03d}'.format(name, startNum)
        return newName
        
    @staticmethod     
    def getUuid(nodeName):
        try:
            mobj = om2.MGlobal.getSelectionListByName(nodeName).getDependNode(0)
            return om2.MFnDependencyNode(mobj).uuid().asString()
        except:
            return  
     
class SpaceSwitchMeta(object):
    _CACHE = {}
    _NODETYPE = 'network'
    
    def __new__(cls, *args, **kwargs):
        nodeName = args[0] if len(args) > 0 else kwargs.get('nodeName')
        
        uuid = MetaUtils.getUuid(nodeName)
        if uuid is None:
            uuid = MetaUtils.getUuid(cls._create(nodeName, cls._NODETYPE))
            
        if uuid in cls._CACHE:
            return cls._CACHE[uuid]
            
        instance = super(SpaceSwitchMeta, cls).__new__(cls)
        cls._CACHE[uuid] = instance
        return instance
        
    def __init__(self, nodeName):
        if not hasattr(self, '_INITOK'):
            self.node    = nodeName
            self._INITOK = True
            
    def __str__(self):
        return self.path
        
    def __repr__(self):
        return "<SpaceSwitchMeta |'{}'>".format(self.node.name())
        
    @classmethod
    def _create(cls, nodeName, nodeType):
        return MetaUtils.createMetaNode(nodeName, nodeType)
            
    @property
    def node(self):
        return self._node
    
    @node.setter
    def node(self, nodeName):
        mobj       = om2.MGlobal.getSelectionListByName(nodeName).getDependNode(0)
        self._node = om2.MFnDependencyNode(mobj)
        
    @property
    def path(self):
        return self.node.name()
        
    # -----------------------------------------------------------------------------------------    
    @property
    def source(self):
        source = cmds.listConnections('{}.source'.format(self), d=False)
        return cmds.ls(source[0], long=True)[0] if source else None
    
    @source.setter
    def source(self, obj):
        cmds.connectAttr('{}.message'.format(obj), '{}.source'.format(self), f=True)
        
    @property
    def offsetGroup(self):
        offsetGroup = cmds.listConnections('{}.offsetGroup'.format(self), d=False)
        return cmds.ls(offsetGroup[0], long=True)[0] if offsetGroup else None
    
    @offsetGroup.setter
    def offsetGroup(self, obj):
        cmds.connectAttr('{}.message'.format(obj), '{}.offsetGroup'.format(self), f=True)
    
    # -----------------------------------------------------------------------------------------
    @property
    def target(self):
        targetWidgets = {}
        # get target count
        spaceTargets = cmds.listConnections('{}.target'.format(self), d=False)
        #print(spaceTargets)
        for index, target in enumerate(spaceTargets):
            targetData = {}
            targetData['attrName']    = cmds.getAttr('{}.target[{}].attrName'.format(self, index))
            targetData['spaceTarget'] = target
            targetWidgets[index] = targetData
            
        return targetWidgets
        
    @target.setter
    def target(self, data):
        for index, widget in enumerate(data.values()):
            target = widget['spaceTarget']
            cmds.connectAttr('{}.message'.format(target), '{}.target[{}].spaceTarget'.format(self, index), f=True)
            attrName = widget['attrName']
            cmds.setAttr('{}.target[{}].attrName'.format(self, index), attrName, typ="string")
            
    @property        
    def spaceLocs(self):
        return cmds.listConnections('{}.spaceLocs'.format(self), d=False) or []
        
    @spaceLocs.setter
    def spaceLocs(self, data):
        offsetGroup, targets = data
        _targets = [value['spaceTarget'] for value in targets.values()]

        for target in _targets:
            #locName = MetaUtils.uniqueName('{}_{}_spaceSwitch_LOC'.format(self.source.split('|')[-1], target.split('|')[-1]))
            locName = MetaUtils.uniqueName('{}_spaceSwitch_LOC'.format(self.source.split('|')[-1]))
            loc = cmds.createNode('transform', name=locName)
            cmds.parent(loc, target)
            cmds.matchTransform(loc, offsetGroup)
            MetaUtils.connectMiAttr(loc, 'message', self, 'spaceLocs')
                
    @property
    def constraints(self):
        _constraints = []
        childAttrs = cmds.attributeQuery('constraints', node=self, listChildren=True)
        for attr in childAttrs:
            cons = cmds.listConnections('{}.constraints.{}'.format(self, attr), d=False)
            if cons is None:
                continue
            _constraints.append(cons[0])
        return _constraints
        
    @constraints.setter
    def constraints(self, data):
        types, offsetGroup, spaceLoc = data
        conTypes = [i for i in types if types[i]]
        for conType in conTypes:
            if conType == 'point':
                c = cmds.pointConstraint(spaceLoc, offsetGroup, mo=True)[0]
                cmds.connectAttr('{}.message'.format(c), '{}.constraints.pointConstraint'.format(self), f=True)
            elif conType == 'orient':
                c = cmds.orientConstraint(spaceLoc, offsetGroup, mo=True)[0]
                cmds.setAttr('{}.interpType'.format(c), 2)
                cmds.connectAttr('{}.message'.format(c), '{}.constraints.orientConstraint'.format(self), f=True)
            elif conType == 'scale':
                c = cmds.scaleConstraint(spaceLoc, offsetGroup, mo=True)[0]
                cmds.connectAttr('{}.message'.format(c), '{}.constraints.scaleConstraint'.format(self), f=True)
            elif conType == 'parent':
                c = cmds.parentConstraint(spaceLoc, offsetGroup, mo=True)[0]
                cmds.setAttr('{}.interpType'.format(c), 2)
                cmds.connectAttr('{}.message'.format(c), '{}.constraints.parentConstraint'.format(self), f=True)
                
    # -----------------------------------------------------------------------------------------
    @property
    def conType(self):
        conTypeDic = {}
        # get childs attr name
        childAttrs = cmds.attributeQuery('constraints', node=self, listChildren=True)
        for attr in childAttrs:
            value = bool(cmds.listConnections('{}.constraints.{}'.format(self, attr)))
            conTypeDic[attr.split('Constraint')[0]] = value
        return conTypeDic
        
    def createAttr(self, ctrl, targets):
        attrNames = [value['attrName'] for value in targets.values()]
        if cmds.attributeQuery('spaceSwitch', node=ctrl, ex=True):
            cmds.deleteAttr('{}.spaceSwitch'.format(ctrl))
        cmds.addAttr(ctrl, ln='spaceSwitch', at='enum', k=True, en=':'.join(attrNames))
    
    # -----------------------------------------------------------------------------------------------
    @property
    def conditionNodes(self):
        return cmds.listConnections('{}.conditionNodes'.format(self), d=False) or []
            
    def createConditionNode(self, ctrl, constraints):
        for cons in constraints:
            for index, loc in enumerate(self.spaceLocs):
                condNodeName = MetaUtils.uniqueName('{}_condition'.format(loc.split('|')[-1]))
                condNode = cmds.createNode('condition', name=condNodeName)
                cmds.setAttr('{}.colorIfTrueR'.format(condNode), 1)
                cmds.setAttr('{}.colorIfFalseR'.format(condNode), 0)
                cmds.setAttr('{}.secondTerm'.format(condNode), index)
                cmds.connectAttr('{}.spaceSwitch'.format(ctrl),   '{}.firstTerm'.format(condNode), f=True)
                cmds.connectAttr('{}.outColorR'.format(condNode), '{}.{}W{}'.format(cons, loc, index), f=True)
                MetaUtils.connectMiAttr(condNode, 'message', self, 'conditionNodes')
                
    @property    
    def offsetGroupMatrix(self):
        return cmds.getAttr('{}.offsetGroupLocalMatrix'.format(self))

    @offsetGroupMatrix.setter
    def offsetGroupMatrix(self, inMatrix):
        cmds.setAttr('{}.offsetGroupLocalMatrix'.format(self), inMatrix, typ='matrix')
    # -----------------------------------------------------------------------------------------
        
    @property
    def nodeData(self):
        _nodeData = {}
        _nodeData['source']        = self.source
        _nodeData['offsetGroup']   = self.offsetGroup
        _nodeData['conType']       = self.conType
        _nodeData['targetWidgets'] = self.target
        return _nodeData
        
    @nodeData.setter    
    def nodeData(self, data):
        self.source = data['source']
        self.offsetGroup = data['offsetGroup']
        self.target = data['targetWidgets']
        self.spaceLocs = (self.offsetGroup, self.target)
        self.offsetGroupMatrix = cmds.xform(self.offsetGroup, q=True, m=True, ws=False)
        
        self.constraints = (data['conType'], self.offsetGroup, self.spaceLocs)
        self.createAttr(self.source, self.target)
        self.createConditionNode(self.source, self.constraints)
        cmds.select(self.source, ne=True)
        
    @nodeData.deleter    
    def nodeData(self):
        cmds.delete(self.conditionNodes, 
                    self.constraints,
                    self.spaceLocs)
        if cmds.attributeQuery('spaceSwitch', node=self.source, ex=True):
            cmds.deleteAttr('{}.spaceSwitch'.format(self.source))
        cmds.xform(self.offsetGroup, m=self.offsetGroupMatrix, ws=False)
        cmds.delete(self)

'''
data =  {'source': 'joint1', 
         'offsetGroup': 'joint1_str', 
         'conType': {'point': False, 'orient': False, 'scale': True, 'parent': True}, 
         'targetWidgets': {0: {'attrName': 'ikk', 'spaceTarget': 'ik'}, 
                           1: {'attrName': 'fkk', 'spaceTarget': 'fk'}}} #        

node = SpaceSwitchMeta('woshikangddan')
node.nodeData = data
node.nodeData
del node.nodeData
nodes = MetaUtils.getMetaNodes()
'''

class LineShape(QtWidgets.QFrame):
    def __init__(self):
        super(LineShape, self).__init__()
        self.setFrameShape(QtWidgets.QFrame.HLine)
        self.setStyleSheet("border-top: 2px solid #505050;")
        
class TargetWidget(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super(TargetWidget, self).__init__(parent)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True) 
        self.setObjectName('baseWidget')
        self.createWidgets()
        self.createLayouts()
        self.createConnections()
        self.spaceTargetLong = None
        
    def setWidgetColor(self, count):
        if count % 2 == 0:
            self.setStyleSheet('#baseWidget { background-color: #373737;}')
        else:
            self.setStyleSheet('#baseWidget { background-color: #444444;}')
        
    def __repr__(self):
        return '<{0}> AttrName: {1} SpaceTarget: {2}'.format(
        self.__class__.__name__, self.attrNameLine.text(), self.spaceTargetLine.text())
        
    def createLayouts(self):
        mainLayout = QtWidgets.QVBoxLayout(self)
        mainLayout.setMargin(8)
        mainLayout.setSpacing(5)
        
        gridLayout = QtWidgets.QGridLayout()
        gridLayout.setSpacing(5)
        gridLayout.addWidget(QtWidgets.QLabel('Attr Name'), 0, 0)
        gridLayout.addWidget(self.attrNameLine, 0, 1, 1, 2)
        gridLayout.addWidget(QtWidgets.QLabel('Space Target'), 1, 0)
        gridLayout.addWidget(self.spaceTargetLine, 1, 1)
        gridLayout.addWidget(self.spaceBut, 1, 2)
        
        mainLayout.addLayout(gridLayout)
        mainLayout.addWidget(LineShape())
        #mainLayout.addStretch()
        
    def createWidgets(self):
        self.attrNameLine = QtWidgets.QLineEdit()
        regex = QtCore.QRegExp('^[a-zA-Z_][a-zA-Z0-9_]*$')
        validator = QtGui.QRegExpValidator(regex, self.attrNameLine)
        self.attrNameLine.setValidator(validator)
        
        # ---------------------------------------
        self.spaceTargetLine  = QtWidgets.QLineEdit()
        self.spaceTargetLine.setReadOnly(True)
        self.spaceBut = QtWidgets.QPushButton()
        self.spaceBut.setIcon(QtGui.QIcon(':moveUVLeft.png'))
        self.spaceBut.setFixedSize(28, 28)

    def createConnections(self):
        self.spaceBut.clicked.connect(self.addSpaceTargetNode)

    def addSpaceTargetNode(self):
        sel = getSelection()

        if not sel:
            return om2.MGlobal.displayWarning('Please select an object')
        if isinstance(sel[0], om2.MFnDependencyNode):
            return om2.MGlobal.displayWarning('Please select an dagNode')
            
        name, longName = getNodeLongName(sel[0])
        self.spaceTargetLine.setText(name)
        self.spaceTargetLong = longName
        
    def getWidgetData(self):
        return {'attrName':self.attrNameLine.text(),
                'spaceTarget':self.spaceTargetLong }
                
    def setWidgetData(self, data):
        self.attrNameLine.setText(data.get('attrName'))
        
        self.spaceTargetLine.setText(data.get('spaceTarget').split('|')[-1])
        self.spaceTargetLong = data.get('spaceTarget')
        

class SpaceSwitchUI(QtWidgets.QDialog):
    INSTANCE = None
    
    def showEvent(self, event):
        if self.geometry:
            self.restoreGeometry(self.geometry)
        #self.getMeta()
        if self.openUI:
            self.createScriptJobs()
            self.openUI = False
        super(SpaceSwitchUI, self).showEvent(event)
        
    def closeEvent(self, event):
        super(SpaceSwitchUI, self).closeEvent(event)
        self.geometry = self.saveGeometry()
        self.deleteScriptJobs()
        self.openUI = True
        
    # --------------------------------------------------------    
    def createScriptJobs(self):
        #print('create')
        self.scriptJobs.append(cmds.scriptJob(event=['NewSceneOpened', partial(self.getMeta)], pro=True)) # new scene
        self.scriptJobs.append(cmds.scriptJob(event=['PostSceneRead', partial(self.getMeta)], pro=True))  # open scene
        self.scriptJobs.append(cmds.scriptJob(event=['Undo', partial(self.undoUpdate)], pro=True))  # undo
        
    def deleteScriptJobs(self):
        #print('delete')
        for jobNumber in self.scriptJobs:
            cmds.evalDeferred('if cmds.scriptJob(exists={0}):\tcmds.scriptJob(kill={0}, force=True)'.format(jobNumber))   
        self.scriptJobs = [] 
    # --------------------------------------------------------  
    def undoUpdate(self):
        TargetBoxitemDatas = [self.targetsBox.itemData(i) 
                              for i in range(self.targetsBox.count())
                              if isinstance(self.targetsBox.itemData(i), SpaceSwitchMeta)]
                              
        metaNodes = MetaUtils.getMetaNodes()
        if not set(TargetBoxitemDatas) == set(metaNodes):
            #print('start undo')
            self._updateUI_()

    def getMeta(self):
        metaNodes = MetaUtils.getMetaNodes()
        self.targetsBox.clear()
        self.targetsBox.addItem('<New>')
        
        for metaNode in metaNodes:
            self.targetsBox.addItem(metaNode.path, metaNode) # metaNode instance to data

        self.updateData()
        
    def resetData(self):
        self.deleteAllTargetWidget()
        self.sourceLineEdit.setText('')
        self.offsetGroupLineEdit.setText('')
        self.positionCheckBox.setChecked(False)
        self.rotationCheckBox.setChecked(False)
        self.scaleCheckBox.setChecked(False)
        self.parentCheckBox.setChecked(False)
        
        self.positionCheckBox.setEnabled(True)
        self.rotationCheckBox.setEnabled(True)
        self.sourceLong = None
        self.offsetGroupLong = None
        
    def updateData(self):
        currentIndex = self.targetsBox.currentIndex()
        itemData = self.targetsBox.itemData(currentIndex)
        if itemData is not None and isinstance(itemData, SpaceSwitchMeta):
            self.setWidgetData(itemData.nodeData) # get metaNode instance data
            cmds.select(itemData.source, ne=True)
        else:   
            self.resetData()
            #cmds.select(cl=True)
    
    def parentTo(self):
        isParent = self.parentCheckBox.isChecked()
        if isParent:
            # get conscheckbox state
            self.pBoxState = self.positionCheckBox.isChecked()
            self.rBoxState = self.rotationCheckBox.isChecked()
            
            self.positionCheckBox.setChecked(False)
            self.positionCheckBox.setEnabled(False)
            self.rotationCheckBox.setChecked(False)
            self.rotationCheckBox.setEnabled(False)
            
        else:
            #try:
            self.positionCheckBox.setChecked(self.pBoxState)
            self.positionCheckBox.setEnabled(True)
            self.rotationCheckBox.setChecked(self.rBoxState)
            self.rotationCheckBox.setEnabled(True)
            #except:
                #pass
    
    # --------------------------------------------------------
        
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
        self.setWindowTitle('Space Switch Tool')
        self.geometry = None
        self.setWindowFlags(QtCore.Qt.WindowType.Window)
        self.resize(380, 450)
        self.setFocusPolicy(QtCore.Qt.StrongFocus); self.setFocus()
        # ---------------------------------------
        self.createWidgets()
        self.createLayouts()
        self.createConnections()
        self.sourceLong = None
        self.offsetGroupLong = None
        self.getMeta()
        
        self.openUI = True
        self.scriptJobs = []
        
    def createLayouts(self):
        mainLayout = QtWidgets.QVBoxLayout(self)
        mainLayout.setMargin(8)
        mainLayout.setSpacing(5)
        
        targetsLayout = QtWidgets.QHBoxLayout()
        targetsLayout.setSpacing(5)
        targetsLayout.addWidget(QtWidgets.QLabel('Meta  Nodes'))
        targetsLayout.addWidget(self.targetsBox)
        targetsLayout.addWidget(self.updateBut)
        targetsLayout.setStretchFactor(self.targetsBox, 1)
        
        gridLayout = QtWidgets.QGridLayout()
        gridLayout.setSpacing(5)
        gridLayout.addWidget(QtWidgets.QLabel('Source'), 0, 0)
        gridLayout.addWidget( self.sourceLineEdit, 0, 1)
        gridLayout.addWidget( self.sourceBut, 0, 2)
        gridLayout.addWidget(QtWidgets.QLabel('Offset Group'), 1, 0)
        gridLayout.addWidget( self.offsetGroupLineEdit, 1, 1)
        gridLayout.addWidget( self.offsetGroupBut, 1, 2)
        
        subLayout = QtWidgets.QHBoxLayout()
        subLayout.setSpacing(2)
        subLayout.addWidget(self.addBut)
        subLayout.addWidget(self.removeBut)
    
        # -----------------------------------------
        self.targetsWidget = QtWidgets.QScrollArea()
        self.targetsWidget.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.targetsWidget.setWidgetResizable(True)
        self.targetsWidget.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        
        innerWidget = QtWidgets.QWidget()
        self.targetsLayout = QtWidgets.QVBoxLayout(innerWidget)
        self.targetsLayout.setSpacing(0)
        self.targetsLayout.setMargin(0)
        self.targetsWidget.setWidget(innerWidget)
        # -----------------------------------------
        butLayout = QtWidgets.QHBoxLayout()
        butLayout.setSpacing(2)
        butLayout.addWidget(self.createBut)
        butLayout.addWidget(self.deleteBut)
        
        # -----------------------------------------
        # buts layout
        consCheckboxLayout = QtWidgets.QHBoxLayout()
        consCheckboxLayout.setSpacing(5)
        consCheckboxLayout.addWidget(self.positionCheckBox)
        consCheckboxLayout.addWidget(self.rotationCheckBox)
        consCheckboxLayout.addWidget(self.scaleCheckBox)
        consCheckboxLayout.addWidget(self.parentCheckBox)
         
        # -----------------------------------------
        mainLayout.addLayout(targetsLayout)
        mainLayout.addWidget(LineShape())
        mainLayout.addLayout(gridLayout)
        mainLayout.addLayout(subLayout)
        mainLayout.addLayout(consCheckboxLayout)
        
        #mainLayout.addWidget(LineShape())
        mainLayout.addWidget(self.targetsWidget)
        mainLayout.addLayout(butLayout)
        #mainLayout.addStretch()
        
    def createWidgets(self):

        self.targetsBox = QtWidgets.QComboBox()
        self.updateBut  = QtWidgets.QPushButton()
        self.updateBut.setFixedSize(26, 26)
        self.updateBut.setIcon(QtGui.QIcon(':refresh.png'))
        # ----------------------------------------
        self.sourceLineEdit = QtWidgets.QLineEdit()
        self.sourceLineEdit.setReadOnly(True)
        self.sourceBut = QtWidgets.QPushButton()
        self.sourceBut.setIcon(QtGui.QIcon(':moveUVLeft.png'))
        
        self.sourceBut.setFixedSize(28, 28)
        self.offsetGroupLineEdit = QtWidgets.QLineEdit()
        self.offsetGroupLineEdit.setReadOnly(True)
        self.offsetGroupBut = QtWidgets.QPushButton()
        self.offsetGroupBut.setIcon(QtGui.QIcon(':moveUVLeft.png'))
        self.offsetGroupBut.setFixedSize(28, 28)
        
        # ----------------------------------------
        self.addBut = QtWidgets.QPushButton('Add')
        self.addBut.setFixedHeight(30)
        self.removeBut = QtWidgets.QPushButton('Remove')
        self.removeBut.setFixedHeight(30)
        
        # ----------------------------------------
        self.positionCheckBox = QtWidgets.QCheckBox('point')
        self.rotationCheckBox = QtWidgets.QCheckBox('orient')
        self.scaleCheckBox = QtWidgets.QCheckBox('Scale')
        self.parentCheckBox = QtWidgets.QCheckBox('Parent')
        
        # ----------------------------------------
        self.createBut = QtWidgets.QPushButton('Create')
        self.createBut.setFixedHeight(30)
        self.deleteBut = QtWidgets.QPushButton('Delete')
        self.deleteBut.setFixedHeight(30)
 
    def createConnections(self):
        self.addBut.clicked.connect(self.addTargetWidget)
        self.removeBut.clicked.connect(self.deleteTargetWidget)
        self.parentCheckBox.clicked.connect(self.parentTo)
        
        self.sourceBut.clicked.connect(self.addSourceNode)
        self.offsetGroupBut.clicked.connect(self.addOffsetGroupNode)

        self.createBut.clicked.connect(self.createSpaceSwitch)
        self.deleteBut.clicked.connect(self.deleteSpaceSwitch)
        
        '''
        The activated signal is only emitted when the user manually selects an item
        it will not be triggered by programmatically selecting an item
        '''
        self.targetsBox.activated.connect(self.updateData)
        
        # update ui
        #self.shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Z"), self)
        #self.shortcut.activated.connect(self._updateUI_)
        self.updateBut.clicked.connect(self._updateUI_)
        
    # ----------------------------------------------------------------    
    def _updateUI_(self):
        itemText = self.targetsBox.currentText() 
        self.getMeta()
        
        # select item
        self.textToItemWidget(itemText)
    
    def textToItemWidget(self, itemText):
        itemTexts = [self.targetsBox.itemText(i) for i in range(self.targetsBox.count())]
        
        if itemText in itemTexts:
            index = self.targetsBox.findText(itemText)
            self.targetsBox.setCurrentIndex(index)
            
            itemData = self.targetsBox.itemData(index)
            if itemData is not None and isinstance(itemData, SpaceSwitchMeta):
                self.setWidgetData(itemData.nodeData) # get metaNode instance data
                return True
        return          
    # --------------------------------------------------------------------------    
    def metaExists(self, obj):
        if not cmds.attributeQuery('spaceSwitch', node=obj, ex=True):
            return 
        outputs = cmds.listConnections('{}.message'.format(obj), s=False) or []
        if not outputs:
            return 
        # -------------------------------------------------------------------------------------    
        metaNodeStrs = [m.path for m in MetaUtils.getMetaNodes()]
        for node in outputs:
            if node not in metaNodeStrs:
                continue
            metaNodeName = metaNodeStrs[metaNodeStrs.index(node)]
            return self.textToItemWidget(metaNodeName)
        # -------------------------------------------------------------------------------------  
        return 
                
    def addSourceNode(self):
        sel = getSelection()
        if not sel:
            return om2.MGlobal.displayWarning('Please select an object')
            
        name, longName = getNodeLongName(sel[0])
        
        
        if self.metaExists(longName):
            return
        # -------------------------------------------------------
        self.sourceLineEdit.setText(name)
        self.sourceLong = longName
        
        if isinstance(sel[0], om2.MFnDependencyNode):
            return
        parent = cmds.listRelatives(longName, p=True, f=True) # get parent longName
        if parent:
            self.offsetGroupLineEdit.setText(parent[0].split('|')[-1])
            self.offsetGroupLong = parent[0]
        
    # -------------------------------------------------------------------------- 
    
    def addOffsetGroupNode(self):
        sel = getSelection()
        if not sel:
            return om2.MGlobal.displayWarning('Please select an object')
        
        if isinstance(sel[0], om2.MFnDependencyNode):
            return om2.MGlobal.displayWarning('Please select an dagNode')
            
        name, longName = getNodeLongName(sel[0])
        self.offsetGroupLineEdit.setText(name)
        self.offsetGroupLong = longName
    # --------------------------------------------------------------------------
    def addTargetWidget(self, data=None):
        count = self.targetsLayout.count()
        targetWidget = TargetWidget()
        if data:
            targetWidget.setWidgetData(data)
        
        if count > 0:
            self.targetsLayout.insertWidget(count-1, targetWidget)
        else:
            self.targetsLayout.addWidget(targetWidget)
            self.targetsLayout.addStretch()
            
        targetWidget.setWidgetColor(self.targetsLayout.count())

    def deleteTargetWidget(self):
        targetWidgets = self.getTargetWidgets()
        if not targetWidgets:
            return
        self.targetsLayout.removeWidget(targetWidgets[-1])
        targetWidgets[-1].deleteLater()
        
    def deleteAllTargetWidget(self):
        for widget in self.getTargetWidgets():
            self.targetsLayout.removeWidget(widget)
            widget.deleteLater()
 
    def getTargetWidgets(self):
        targetWidgets = [self.targetsLayout.itemAt(i).widget() for i in range(self.targetsLayout.count()-1)]
 
        return targetWidgets
        
    # ---------------------------------------------------------------
    def getWidgetData(self):
        data = {}
        data['source']      = self.sourceLong
        data['offsetGroup'] = self.offsetGroupLong
        data['conType']     = {'point':self.positionCheckBox.isChecked(),
                               'orient':self.rotationCheckBox.isChecked(),
                               'scale'   :self.scaleCheckBox.isChecked(),
                               'parent'  :self.parentCheckBox.isChecked()}
                               
        targetWidgetsData = {}
        for index, widget in enumerate(self.getTargetWidgets()):
            targetWidgetsData[index] = widget.getWidgetData()
        
        data['targetWidgets'] = targetWidgetsData
        return data
        
    def setWidgetData(self, data):

        self.sourceLineEdit.setText(data.get('source').split('|')[-1])
        self.sourceLong = data.get('source')
        self.offsetGroupLineEdit.setText(data.get('offsetGroup').split('|')[-1])
        self.offsetGroupLong = data.get('offsetGroup')
        
        # ------------------------------------------------------------------------

        self.positionCheckBox.setChecked(data.get('conType')['point'])
        self.rotationCheckBox.setChecked(data.get('conType')['orient'])
        self.scaleCheckBox.setChecked(data.get('conType')['scale'])
        self.parentCheckBox.setChecked(data.get('conType')['parent'])
        
        # --------------------------------------------------
        # update checkbox state
        self.pBoxState = data.get('conType')['point']
        self.rBoxState = data.get('conType')['orient']
        self.parentTo()
        
        # ------------------------------------------------------------------------
        self.deleteAllTargetWidget()
        targetWidgets = data.get('targetWidgets', [])
        for i in range(len(targetWidgets)):
            self.addTargetWidget(targetWidgets[i])
            
    # --------------------------------------------------------------------------------
    def deleteTargetItemAndMeta(self):

        currentIndex = self.targetsBox.currentIndex()      
        itemData = self.targetsBox.itemData(currentIndex)
        if itemData is not None and isinstance(itemData, SpaceSwitchMeta):
            del itemData.nodeData
            self.targetsBox.removeItem(currentIndex)
            
    # -----------------------------------------------------------------------------       
    def checkDuplicateValue(self, data, key):
        values = set()
        for item in data.values():
            value = item[key]
            if value in values:
                return False
            values.add(value)
        return True
            
    def checkData(self, data):

        # ----------------------------------------------------------------     
        if data['source'] is None or data['offsetGroup'] is None:
            return om2.MGlobal.displayWarning('Invalid parameter')
            
        if data['source'] == data['offsetGroup']:
            return om2.MGlobal.displayWarning('Invalid parameter')
        
        
        if True not in data['conType'].values():
            return om2.MGlobal.displayWarning('Invalid constraint type')


        targetWidgetsData = data['targetWidgets']
        if not targetWidgetsData:
            return om2.MGlobal.displayWarning('Please add at least one space switch')
        
        if False in [bool(widget['attrName']) for widget in targetWidgetsData.values()]:
            return om2.MGlobal.displayWarning('Invalid attribute name')
            
 
        if None in [widget['spaceTarget'] for widget in targetWidgetsData.values()]:
            return om2.MGlobal.displayWarning('Invalid target object')
            
        '''
        avoid having identical targets/attrName, which could cause us to lose the constraint objects
        '''    
        
        if not self.checkDuplicateValue(targetWidgetsData, 'attrName'):
            return om2.MGlobal.displayWarning('Having the same attribute name')    
            
        if not self.checkDuplicateValue(targetWidgetsData, 'spaceTarget'):
            return om2.MGlobal.displayWarning('Having the same target object')
            
        return True
        
    # -----------------------------------------------------------------------------       
    @addUndo        
    def createSpaceSwitch(self): 
        data = self.getWidgetData()
  
        if not self.checkData(data):
            return

        # ---------------------------------------------------------------- 
        self.deleteTargetItemAndMeta()
 
        # ----------------------------------------------------------------
        metaNodeName = MetaUtils.uniqueName('{}_spaceSwitch_META'.format(data['source'].split('|')[-1]))
        metaNodeInstance = SpaceSwitchMeta(metaNodeName)
        metaNodeInstance.nodeData = data
        self.targetsBox.addItem(metaNodeInstance.path, metaNodeInstance) # add instance to item data
        self.targetsBox.setCurrentText(metaNodeInstance.path)
      
    @addUndo  
    def deleteSpaceSwitch(self):
        
        self.deleteTargetItemAndMeta()
        self.updateData()
        
    
if __name__ == '__main__':
    SpaceSwitchUI.displayUI()
