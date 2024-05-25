import maya.cmds         as cmds
import maya.api.OpenMaya as om2
import PySide2.QtWidgets as QtWidgets
import PySide2.QtCore    as QtCore
import PySide2.QtGui     as QtGui

# -----------------------------------------------------------------------------------    

class MetaNode(object):
    INSTANCE_CACHE = {}
    def __new__(cls, *args, **kwargs):
        nodeName = args[0] if len(args) > 0 else kwargs.get('nodeName')
        
        uuid = cmds.ls(nodeName, uid=True)[0]
        if uuid in cls.INSTANCE_CACHE:
            return cls.INSTANCE_CACHE[uuid]
            
        instance = super(MetaNode, cls).__new__(cls)
        cls.INSTANCE_CACHE[uuid] = instance
        return instance
    
    def __init__(self, nodeName):
        if not hasattr(self, '_INITOK'):
            self.apiObject = nodeName
            self._INITOK = True

    @property
    def apiObject(self):
        return self._node
    
    @apiObject.setter
    def apiObject(self, nodeName):
        mobj = om2.MGlobal.getSelectionListByName(nodeName).getDependNode(0)
        self._node = om2.MFnDependencyNode(mobj)
        
    @property
    def node(self):
        return self.apiObject.name()
    
    @property
    def uuid(self):
        return self.apiObject.uuid().asString()
       
    # ----------------------------------------------------------------------------------------------------
    @property
    def source(self):
        return cmds.listConnections('{}.source'.format(self.node), d=False) or []
    
    @source.setter
    def source(self, obj):
        if cmds.isConnected('{}.message'.format(obj), '{}.source'.format(self.node)):
            return
        cmds.connectAttr('{}.message'.format(obj), '{}.source'.format(self.node), f=True)
        
    @property
    def offsetGroup(self):
        return cmds.listConnections('{}.offsetGroup'.format(self.node), d=False) or []
    
    @offsetGroup.setter
    def offsetGroup(self, obj):
        if cmds.isConnected('{}.message'.format(obj), '{}.offsetGroup'.format(self.node)):
            return
        cmds.connectAttr('{}.message'.format(obj), '{}.offsetGroup'.format(self.node), f=True)
   
    @property
    def target(self):
        targetWidgets = {}
        # get target count
        spaceTargets = cmds.listConnections('{}.target'.format(self.node), d=False)
        for index, target in enumerate(spaceTargets):
            targetData = {}
            targetData['attrName']    = cmds.getAttr('{}.target[{}].attrName'.format(self.node, index))
            targetData['spaceTarget'] = cmds.ls(target, uid=True)[0]
            targetWidgets[index] = targetData
            
        return targetWidgets
        
    @target.setter
    def target(self, data):
        for index, widget in enumerate(data.values()):
            target = cmds.ls(widget['spaceTarget'])[0]
            cmds.connectAttr('{}.message'.format(target), '{}.target[{}].spaceTarget'.format(self.node, index), f=True)
            
            attrName = widget['attrName']
            cmds.setAttr('{}.target[{}].attrName'.format(self.node, index), attrName, typ="string")
    
    # -----------------------------------------------------------------------------------------------------      
    def createAttr(self, ctrl, targets):
        attrNames = [value['attrName'] for value in targets.values()]
        if cmds.attributeQuery('spaceSwitch', node=ctrl, ex=True):
            cmds.deleteAttr('{}.spaceSwitch'.format(ctrl))
            
        cmds.addAttr(ctrl, ln='spaceSwitch', at='enum', k=True, en=':'.join(attrNames))
    # -----------------------------------------------------------------------------------------------------  
    @property
    def toConstraints(self):
        constraints = []
        childAttrs = cmds.attributeQuery('constraints', node=self.node, listChildren=True)
        for attr in childAttrs:
            cons = cmds.listConnections('{}.constraints.{}'.format(self.node, attr), d=False)
            if cons is None:
                continue
            constraints.append(cons[0])
        return constraints

    def createSwitchNode(self, ctrl):
        # get constraints
        constraints = self.toConstraints

        for cons in constraints:
            for index, loc in enumerate(self.spaceLocs):
                condNode = cmds.createNode('condition', name='{}_condition'.format(loc))
                cmds.setAttr('{}.colorIfTrueR'.format(condNode), 1)
                cmds.setAttr('{}.colorIfFalseR'.format(condNode), 0)
                cmds.setAttr('{}.secondTerm'.format(condNode), index)
                cmds.connectAttr('{}.spaceSwitch'.format(ctrl),   '{}.firstTerm'.format(condNode), f=True)
                cmds.connectAttr('{}.outColorR'.format(condNode), '{}.{}W{}'.format(cons, loc, index), f=True)
                MetaUtils.connectMiAttr(condNode, 'message', self.node, 'conditionNodes')
                
    @property
    def conditionNodes(self):
        return cmds.listConnections('{}.conditionNodes'.format(self.node), d=False) or []
        
    @property        
    def spaceLocs(self):
        return cmds.listConnections('{}.spaceLocs'.format(self.node), d=False) or []
        
    @spaceLocs.setter
    def spaceLocs(self, data):
        offsetGroup, targets = data
        _targets = [cmds.ls(value['spaceTarget'])[0] for value in targets.values()]

        for target in _targets:
            loc = cmds.createNode('transform', name='{}_{}_spaceSwitch_LOC'.format(self.source[0], target))
            cmds.parent(loc, target)
            cmds.matchTransform(loc, offsetGroup)
            MetaUtils.connectMiAttr(loc, 'message', self.node, 'spaceLocs')
        
      
    def createConstrain(self, types, offsetGroup=None):
        spaceLoc = self.spaceLocs
        conTypes = [i for i in types if types[i]]
        
        for conType in conTypes:
            if conType == 'position':
                c = cmds.pointConstraint(spaceLoc, offsetGroup, mo=True)[0]
                cmds.connectAttr('{}.message'.format(c), '{}.constraints.positionConstraint'.format(self.node), f=True)
            elif conType == 'rotation':
                c = cmds.orientConstraint(spaceLoc, offsetGroup, mo=True)[0]
                cmds.setAttr('{}.interpType'.format(c), 2)
                cmds.connectAttr('{}.message'.format(c), '{}.constraints.rotationConstraint'.format(self.node), f=True)
            elif conType == 'scale':
                c = cmds.scaleConstraint(spaceLoc, offsetGroup, mo=True)[0]
                cmds.connectAttr('{}.message'.format(c), '{}.constraints.scaleConstraint'.format(self.node), f=True)
            elif conType == 'parent':
                c = cmds.parentConstraint(spaceLoc, offsetGroup, mo=True)[0]
                cmds.setAttr('{}.interpType'.format(c), 2)
                cmds.connectAttr('{}.message'.format(c), '{}.constraints.parentConstraint'.format(self.node), f=True)
                
    # -----------------------------------------------------------------------------------------------------  
    
    def getConType(self):
        conTypeDic = {}
        # get childs attr name
        childAttrs = cmds.attributeQuery('constraints', node=self.node, listChildren=True)
        for attr in childAttrs:
            value = bool(cmds.listConnections('{}.constraints.{}'.format(self.node, attr)))
            conTypeDic[attr.split('Constraint')[0]] = value
        return conTypeDic
 
    # --------------------------------------------------------------------------------------------------
    def setData(self, data):
        self.source = cmds.ls(data['source'])[0]
        self.offsetGroup = cmds.ls(data['offsetGroup'])[0]
        self.target = data['targetWidgets']
        self.spaceLocs = (self.offsetGroup[0], self.target)
        self.offsetGroupMatrix = cmds.xform(self.offsetGroup[0], q=True, m=True, ws=False)
        
        self.createConstrain(data['conType'], self.offsetGroup[0])
        self.createAttr(self.source[0], self.target)
        self.createSwitchNode(self.source[0])
        cmds.select(self.source[0], ne=True)
        
        
    def getData(self):
        metaData = {}
        metaData['source']        = cmds.ls(self.source[0], uid=True)[0]
        metaData['offsetGroup']   = cmds.ls(self.offsetGroup[0], uid=True)[0]
        metaData['conType']       = self.getConType()
        metaData['targetWidgets'] = self.target
        return metaData
        
    def deleteMeta(self):
        cmds.delete(self.conditionNodes, 
                    self.toConstraints,
                    self.spaceLocs)
        if cmds.attributeQuery('spaceSwitch', node=self.source[0], ex=True):
            cmds.deleteAttr('{}.spaceSwitch'.format(self.source[0]))
        cmds.xform(self.offsetGroup[0], m=self.offsetGroupMatrix, ws=False)
        cmds.delete(self.node)
    
    @property    
    def offsetGroupMatrix(self):
        return cmds.getAttr('{}.offsetGroupLocalMatrix'.format(self.node))
    
    
    @offsetGroupMatrix.setter
    def offsetGroupMatrix(self, inMatrix):
        cmds.setAttr('{}.offsetGroupLocalMatrix'.format(self.node), inMatrix, typ='matrix')
    
# -----------------------------------------------------------------------------------     

def uniqueName(name):
    startNum = 0; newName = name
    while cmds.objExists(newName):
        startNum += 1
        newName = '{}_{:03d}'.format(name, startNum)
    return newName    

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
        
        
class MetaUtils(object):
    _NODETYPE_   = 'network'
    _META_VALUE_ = 'spaceSwitch'
    
    @classmethod
    def getMetaNodes(cls):
        return [node for node in cmds.ls(typ=cls._NODETYPE_)
                if cmds.attributeQuery('metaType', n=node, ex=True) and 
                cmds.getAttr('{}.metaType'.format(node)) == cls._META_VALUE_]
    
    @classmethod
    def connectMiAttr(cls, node, attr, metaNode, metaAttr):
        index = 0  
        while True:
            fullPathAttr = '{}.{}[{}]'.format(metaNode, metaAttr, index)
            if cmds.listConnections(fullPathAttr, d=False) is None:
                cmds.connectAttr('{}.{}'.format(node, attr), fullPathAttr, f=True)
                break   
            index += 1 
        
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
        cmds.addAttr(metaNode, ln='target', nc=2, at='compound', m=True)
        cmds.addAttr(metaNode, ln='attrName', dt='string', p='target')
        cmds.addAttr(metaNode, ln='spaceTarget', at='message', p='target')
        # ----------------------------------------------------
        cmds.addAttr(metaNode, ln='spaceLocs', dt='string', m=True)
        cmds.addAttr(metaNode, ln='conditionNodes', dt='string', m=True)
        cmds.addAttr(metaNode, ln='offsetGroupLocalMatrix', dt="matrix")
        return metaNode
        
    @classmethod
    def isUuidValid(cls, uuid):
        if isinstance(uuid, str):
            return om2.MUuid(uuid).valid()
        elif isinstance(uuid, om2.MUuid):
            return uuid.valid()
        return False
            

# ---------------------------------------------------------------------------------------------------------    
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
        self.spaceTargetUUID = None
        
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
        sel = cmds.ls(sl=True, long=True)
        if not sel:
            return om2.MGlobal.displayWarning('Please select an object')
        
        self.spaceTargetLine.setText(sel[0].split('|')[-1])
        self.spaceTargetUUID = cmds.ls(sel[0], uid=True)[0]
        
    def getWidgetData(self):
        return {'attrName':self.attrNameLine.text(),
                'spaceTarget':self.spaceTargetUUID }
    def setWidgetData(self, data):
        self.attrNameLine.setText(data.get('attrName'))
 
        self.spaceTargetLine.setText(cmds.ls(data.get('spaceTarget'))[0])
        self.spaceTargetUUID = data.get('spaceTarget')
        

class SpaceSwitchUI(QtWidgets.QDialog):
    INSTANCE = None
    
    def showEvent(self, event):
        if self.geometry:
            self.restoreGeometry(self.geometry)
        #self.getMeta()
        super(SpaceSwitchUI, self).showEvent(event)
        
    # --------------------------------------------------------    
    
    def getMeta(self):
        metaNodes = MetaUtils.getMetaNodes()
        self.targetsBox.clear()
        self.targetsBox.addItem('<New>')
        
        for nodeName in metaNodes:
            self.targetsBox.addItem(nodeName, MetaNode(nodeName)) # metaNode instance to data

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
        self.sourceUUID = None
        self.offsetGroupUUID = None
        
    def updateData(self):
        currentIndex = self.targetsBox.currentIndex()
        itemData = self.targetsBox.itemData(currentIndex)
        if itemData is not None and isinstance(itemData, MetaNode):
            self.setWidgetData(itemData.getData()) # get metaNode instance data
            cmds.select(itemData.source[0], ne=True)
        else:   
            self.resetData()
            #cmds.select(cl=True)
    
    # --------------------------------------------------------
            
    def closeEvent(self, event):
        super(SpaceSwitchUI, self).closeEvent(event)
        self.geometry = self.saveGeometry()
        #self.getMeta()
        
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
        self.sourceUUID = None
        self.offsetGroupUUID = None
        self.getMeta()
        
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
        self.positionCheckBox = QtWidgets.QCheckBox('Position')
        self.rotationCheckBox = QtWidgets.QCheckBox('Rotation')
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
        
    def _updateUI_(self):
        itemText = self.targetsBox.currentText() 
        self.getMeta()
        
        # select item
        if itemText in [self.targetsBox.itemText(i) for i in range(self.targetsBox.count())]:
            index = self.targetsBox.findText(itemText)
            self.targetsBox.setCurrentIndex(index)
            
            itemData = self.targetsBox.itemData(index)
            if itemData is not None and isinstance(itemData, MetaNode):
                self.setWidgetData(itemData.getData()) # get metaNode instance data
    # --------------------------------------------------------------------------    

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
        
    def addSourceNode(self):
        sel = cmds.ls(sl=True, long=True)
        if not sel:
            return om2.MGlobal.displayWarning('Please select an object')
        
        self.sourceLineEdit.setText(sel[0].split('|')[-1])
        self.sourceUUID = cmds.ls(sel[0], uid=True)[0]
        
        parent = cmds.listRelatives(sel[0], p=True, f=True) # add parent name
        if parent:
            self.offsetGroupLineEdit.setText(parent[0].split('|')[-1])
            self.offsetGroupUUID = cmds.ls(parent[0], uid=True)[0]
        else:
            self.offsetGroupLineEdit.setText('')
            self.offsetGroupUUID = None
            
    def addOffsetGroupNode(self):
        sel = cmds.ls(sl=True, long=True)
        if not sel:
            return om2.MGlobal.displayWarning('Please select an object')
        
        self.offsetGroupLineEdit.setText(sel[0].split('|')[-1])
        self.offsetGroupUUID = cmds.ls(sel[0], uid=True)[0]
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
        data['source']      = self.sourceUUID
        data['offsetGroup'] = self.offsetGroupUUID
        data['conType']     = {'position':self.positionCheckBox.isChecked(),
                               'rotation':self.rotationCheckBox.isChecked(),
                               'scale'   :self.scaleCheckBox.isChecked(),
                               'parent'  :self.parentCheckBox.isChecked()}
                               
        targetWidgetsData = {}
        for index, widget in enumerate(self.getTargetWidgets()):
            targetWidgetsData[index] = widget.getWidgetData()
        
        data['targetWidgets'] = targetWidgetsData
        return data
        
    def setWidgetData(self, data):

        self.sourceLineEdit.setText(cmds.ls(data.get('source'))[0])
        self.sourceUUID = data.get('source')
        self.offsetGroupLineEdit.setText(cmds.ls(data.get('offsetGroup'))[0])
        self.offsetGroupUUID = data.get('offsetGroup')
        
        # ------------------------------------------------------------------------

        self.positionCheckBox.setChecked(data.get('conType')['position'])
        self.rotationCheckBox.setChecked(data.get('conType')['rotation'])
        self.scaleCheckBox.setChecked(data.get('conType')['scale'])
        self.parentCheckBox.setChecked(data.get('conType')['parent'])
        
        # --------------------------------------------------
        # update checkbox state
        self.pBoxState = data.get('conType')['position']
        self.rBoxState = data.get('conType')['rotation']
        self.parentTo()
        
        # ------------------------------------------------------------------------
        self.deleteAllTargetWidget()
        targetWidgets = data.get('targetWidgets', [])
        for i in range(len(targetWidgets)):
            self.addTargetWidget(targetWidgets[i])
            
    # --------------------------------------------------------------------------------
    def deleteTargetItemAndMeta(self):
        '''
        itemText = self.targetsBox.currentText() 
        if itemText in MetaUtils.getMetaNodes():
            MetaNode(itemText).deleteMeta()
            index = self.targetsBox.findText(itemText)
            if index != -1: 
                self.targetsBox.removeItem(index)
        ''' 
        currentIndex = self.targetsBox.currentIndex()      
        itemData = self.targetsBox.itemData(currentIndex)
        if itemData is not None and isinstance(itemData, MetaNode):
            itemData.deleteMeta()
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
        # uuid to string
        sourceFullPathName = cmds.ls(data['source'])[0]
        metaNodeInstance  = MetaNode(MetaUtils.createMetaNode(sourceFullPathName))
        metaNodeInstance.setData(data)
        self.targetsBox.addItem(metaNodeInstance.node, metaNodeInstance) # add instance to item data
        self.targetsBox.setCurrentText(metaNodeInstance.node)
      
    @addUndo  
    def deleteSpaceSwitch(self):
        
        self.deleteTargetItemAndMeta()
        self.updateData()
        
    
if __name__ == '__main__':
    SpaceSwitchUI.displayUI()
