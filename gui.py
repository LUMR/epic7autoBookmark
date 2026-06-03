"""GUI 模块 — PyQt6 图形界面。

修复 Bug #6：expectNum == 0 时弹出错误提示。
修复 Bug #7：字体设置提取为 _make_font() 辅助函数。
修复 Bug #3：停止按钮使用 worker.stop() 替代 worker.terminate()。
"""

from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets

from config import AppConfig
from worker import Worker


def _make_font(family: str = "微軟正黑體", size: int = 12) -> QtGui.QFont:
    """创建共享字体对象。修复 Bug #7：避免字体设置重复 16 次。"""
    font = QtGui.QFont()
    font.setFamily(family)
    font.setPointSize(size)
    return font


class Ui_Main:
    """主窗口 UI。"""

    start = False

    def setupUi(self, Main: QtWidgets.QWidget) -> None:
        # 加载配置获取默认值
        try:
            config = AppConfig.load()
            defaults = config.ui_defaults
        except Exception:
            defaults = {
                "money": "100000000",
                "stone": "30000",
                "covenant": "0",
                "mystic": "0",
                "stone_usage": "99",
            }

        # 共享字体
        font_main = _make_font("微軟正黑體", 12)
        font_log = _make_font("微軟正黑體", 10)
        font_link = _make_font("微軟正黑體", 11)

        # 主窗口
        Main.setObjectName("Main")
        Main.resize(310, 460)
        Main.setMinimumSize(QtCore.QSize(310, 500))
        Main.setMaximumSize(QtCore.QSize(310, 500))
        Main.setFont(font_main)

        # Tab 控件
        self.tabWidget = QtWidgets.QTabWidget(Main)
        self.tabWidget.setGeometry(QtCore.QRect(5, 5, 300, 490))
        self.tabWidget.setMinimumSize(QtCore.QSize(300, 490))
        self.tabWidget.setMaximumSize(QtCore.QSize(300, 490))
        self.tabWidget.setFont(font_main)
        self.tabWidget.setStyleSheet("")
        self.tabWidget.setObjectName("tabWidget")

        # ---- 功能 Tab ----
        self.functionTab = QtWidgets.QWidget()
        self.functionTab.setMinimumSize(QtCore.QSize(300, 490))
        self.functionTab.setMaximumSize(QtCore.QSize(300, 490))
        self.functionTab.setFont(font_main)
        self.functionTab.setObjectName("functionTab")

        # 金币标签
        self.moneyTextShowLabel = QtWidgets.QLabel(self.functionTab)
        self.moneyTextShowLabel.setGeometry(QtCore.QRect(40, 10, 60, 20))
        self.moneyTextShowLabel.setFont(font_main)
        self.moneyTextShowLabel.setObjectName("moneyTextShowLabel")

        # 金币输入框
        self.moneyTotalShowEdit = QtWidgets.QLineEdit(self.functionTab)
        self.moneyTotalShowEdit.setGeometry(QtCore.QRect(120, 10, 111, 20))
        self.moneyTotalShowEdit.setFont(font_main)
        self.moneyTotalShowEdit.setLayoutDirection(QtCore.Qt.LayoutDirection.RightToLeft)
        self.moneyTotalShowEdit.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight
            | QtCore.Qt.AlignmentFlag.AlignTrailing
            | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.moneyTotalShowEdit.setObjectName("moneyTotalShowEdit")

        # 天空石标签
        self.stoneTextShowLabel = QtWidgets.QLabel(self.functionTab)
        self.stoneTextShowLabel.setGeometry(QtCore.QRect(40, 40, 60, 20))
        self.stoneTextShowLabel.setFont(font_main)
        self.stoneTextShowLabel.setObjectName("stoneTextShowLabel")

        # 天空石输入框
        self.stoneTotalShowEdit = QtWidgets.QLineEdit(self.functionTab)
        self.stoneTotalShowEdit.setGeometry(QtCore.QRect(119, 40, 111, 20))
        self.stoneTotalShowEdit.setFont(font_main)
        self.stoneTotalShowEdit.setLayoutDirection(QtCore.Qt.LayoutDirection.RightToLeft)
        self.stoneTotalShowEdit.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight
            | QtCore.Qt.AlignmentFlag.AlignTrailing
            | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.stoneTotalShowEdit.setObjectName("stoneTotalShowEdit")

        # 分隔线
        self.divider = QtWidgets.QFrame(self.functionTab)
        self.divider.setGeometry(QtCore.QRect(10, 60, 271, 20))
        self.divider.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        self.divider.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.divider.setObjectName("divider")

        # 圣约 Radio + 输入
        self.covenantRadioButton = QtWidgets.QRadioButton(self.functionTab)
        self.covenantRadioButton.setGeometry(QtCore.QRect(40, 130, 91, 21))
        self.covenantRadioButton.setChecked(False)
        self.covenantRadioButton.setObjectName("covenantRadioButton")

        self.covenantInput = QtWidgets.QLineEdit(self.functionTab)
        self.covenantInput.setGeometry(QtCore.QRect(140, 130, 70, 20))
        self.covenantInput.setFont(font_main)
        self.covenantInput.setLayoutDirection(QtCore.Qt.LayoutDirection.RightToLeft)
        self.covenantInput.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight
            | QtCore.Qt.AlignmentFlag.AlignTrailing
            | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.covenantInput.setObjectName("covenantInput")

        self.covenantTimeLabel = QtWidgets.QLabel(self.functionTab)
        self.covenantTimeLabel.setGeometry(QtCore.QRect(220, 130, 20, 20))
        self.covenantTimeLabel.setObjectName("covenantTimeLabel")

        # 神秘 Radio + 输入
        self.mysticRadioButton = QtWidgets.QRadioButton(self.functionTab)
        self.mysticRadioButton.setGeometry(QtCore.QRect(40, 170, 91, 21))
        self.mysticRadioButton.setObjectName("mysticRadioButton")

        self.mysticInput = QtWidgets.QLineEdit(self.functionTab)
        self.mysticInput.setGeometry(QtCore.QRect(140, 170, 70, 20))
        self.mysticInput.setFont(font_main)
        self.mysticInput.setLayoutDirection(QtCore.Qt.LayoutDirection.RightToLeft)
        self.mysticInput.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight
            | QtCore.Qt.AlignmentFlag.AlignTrailing
            | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.mysticInput.setObjectName("mysticInput")

        self.mysticTimeLabel = QtWidgets.QLabel(self.functionTab)
        self.mysticTimeLabel.setGeometry(QtCore.QRect(220, 170, 20, 20))
        self.mysticTimeLabel.setObjectName("mysticTimeLabel")

        # 天空石 Radio + 输入
        self.stoneRadioButton = QtWidgets.QRadioButton(self.functionTab)
        self.stoneRadioButton.setGeometry(QtCore.QRect(40, 210, 91, 21))
        self.stoneRadioButton.setChecked(True)
        self.stoneRadioButton.setObjectName("stoneRadioButton")

        self.stoneInput = QtWidgets.QLineEdit(self.functionTab)
        self.stoneInput.setGeometry(QtCore.QRect(140, 210, 70, 20))
        self.stoneInput.setFont(font_main)
        self.stoneInput.setLayoutDirection(QtCore.Qt.LayoutDirection.RightToLeft)
        self.stoneInput.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight
            | QtCore.Qt.AlignmentFlag.AlignTrailing
            | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.stoneInput.setObjectName("stoneInput")

        self.stoneTimeLabel = QtWidgets.QLabel(self.functionTab)
        self.stoneTimeLabel.setGeometry(QtCore.QRect(220, 210, 20, 20))
        self.stoneTimeLabel.setObjectName("stoneTimeLabel")

        # 日志
        self.logTextBrowser = QtWidgets.QTextBrowser(self.functionTab)
        self.logTextBrowser.setGeometry(QtCore.QRect(40, 250, 200, 131))
        self.logTextBrowser.setFont(font_log)
        self.logTextBrowser.setObjectName("logTextBrowser")

        # 开始按钮
        self.startButton = QtWidgets.QPushButton(self.functionTab)
        self.startButton.setGeometry(QtCore.QRect(140, 400, 100, 40))
        self.startButton.setFont(font_main)
        self.startButton.setStyleSheet("")
        self.startButton.setDefault(False)
        self.startButton.setFlat(False)
        self.startButton.setObjectName("startButton")
        self.startButton.clicked.connect(self.startPressEvent)

        self.tabWidget.addTab(self.functionTab, "")

        # ---- 简介 Tab ----
        self.introductionTab = QtWidgets.QWidget()
        self.introductionTab.setMinimumSize(QtCore.QSize(300, 450))
        self.introductionTab.setMaximumSize(QtCore.QSize(300, 450))
        self.introductionTab.setFont(font_main)
        self.introductionTab.setObjectName("introductionTab")

        self.textBrowser = QtWidgets.QTextBrowser(self.introductionTab)
        self.textBrowser.setGeometry(QtCore.QRect(20, 200, 256, 192))
        self.textBrowser.setObjectName("textBrowser")

        self.githubText = QtWidgets.QLabel(self.introductionTab)
        self.githubText.setGeometry(QtCore.QRect(20, 20, 61, 20))
        self.githubText.setFont(font_main)
        self.githubText.setObjectName("githubText")

        self.githubTextUrl = QtWidgets.QLabel(self.introductionTab)
        self.githubTextUrl.setGeometry(QtCore.QRect(20, 40, 251, 41))
        self.githubTextUrl.setFont(font_link)
        self.githubTextUrl.setScaledContents(False)
        self.githubTextUrl.setWordWrap(True)
        self.githubTextUrl.setOpenExternalLinks(True)
        self.githubTextUrl.setObjectName("githubTextUrl")

        self.tabWidget.addTab(self.introductionTab, "")

        # ---- Worker ----
        self.worker = Worker()
        self.worker.isStart.connect(self.startWorker)
        self.worker.isFinish.connect(self.stopWorker)
        self.worker.isError.connect(self.errorWorker)
        self.worker.emitLog.connect(lambda text: self.logTextBrowser.append(text))
        self.worker.emitMoney.connect(lambda text: self.moneyTotalShowEdit.setText(text))
        self.worker.emitStone.connect(lambda text: self.stoneTotalShowEdit.setText(text))

        self.retranslateUi(Main, defaults)
        self.tabWidget.setCurrentIndex(0)
        QtCore.QMetaObject.connectSlotsByName(Main)

    def retranslateUi(self, Main: QtWidgets.QWidget, defaults: dict[str, str]) -> None:
        _translate = QtCore.QCoreApplication.translate

        Main.setWindowTitle(_translate("Main", "第七史詩刷商店小工具"))
        self.covenantInput.setText(_translate("Main", defaults["covenant"]))
        self.mysticInput.setText(_translate("Main", defaults["mystic"]))
        self.moneyTextShowLabel.setText(_translate("Main", "金幣"))
        self.moneyTotalShowEdit.setText(_translate("Main", defaults["money"]))
        self.stoneTextShowLabel.setText(_translate("Main", "天空石"))
        self.stoneTotalShowEdit.setText(_translate("Main", defaults["stone"]))
        self.startButton.setText(_translate("Main", "開始"))
        self.covenantTimeLabel.setText(_translate("Main", "次"))
        self.mysticTimeLabel.setText(_translate("Main", "次"))
        self.logTextBrowser.setHtml(
            _translate(
                "Main",
                '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0//EN" "http://www.w3.org/TR/REC-html40/strict.dtd">\n'
                '<html><head><meta name="qrichtext" content="1" /><style type="text/css">\n'
                "p, li { white-space: pre-wrap; }\n"
                "</style></head><body style=\" font-family:'微軟正黑體'; font-size:10pt; font-weight:400; font-style:normal;\">\n"
                '<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">毫無反應, 就是個小工具</p></body></html>',
            )
        )
        self.stoneTimeLabel.setText(_translate("Main", "個"))
        self.stoneInput.setText(_translate("Main", defaults["stone_usage"]))
        self.covenantRadioButton.setText(_translate("Main", "聖約書籤"))
        self.mysticRadioButton.setText(_translate("Main", "神秘書籤"))
        self.stoneRadioButton.setText(_translate("Main", "天空石"))
        self.tabWidget.setTabText(
            self.tabWidget.indexOf(self.functionTab), _translate("Main", "功能")
        )
        self.textBrowser.setHtml(
            _translate(
                "Main",
                '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0//EN" "http://www.w3.org/TR/REC-html40/strict.dtd">\n'
                '<html><head><meta name="qrichtext" content="1" /><style type="text/css">\n'
                "p, li { white-space: pre-wrap; }\n"
                "</style></head><body style=\" font-family:'微軟正黑體'; font-size:10pt; font-weight:400; font-style:normal;\">\n"
                '<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><span style=" font-weight:600;">功能說明</span></p>\n'
                '<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">自動在秘密商店尋找並購買聖約書籤和神秘書籤</p>\n'
                '<p style="-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><br /></p>\n'
                '<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><span style=" font-weight:600;">使用方式</span></p>\n'
                '<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">1. 填寫持有的金幣和天空石數量</p>\n'
                '<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">2. 選擇停止條件（聖約次數 / 神秘次數 / 天空石消耗量）</p>\n'
                '<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">3. 點擊「開始」</p>\n'
                '<p style="-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><br /></p>\n'
                '<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><span style=" font-weight:600;">啟動條件</span></p>\n'
                '<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">• 金幣至少 280,000</p>\n'
                '<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">• 天空石至少 3</p>\n'
                '<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">• 遊戲視窗需要可見</p>\n'
                '<p style="-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><br /></p>\n'
                '<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><span style=" font-weight:600;">注意事項</span></p>\n'
                '<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">• 刷到的聖約與神秘都會購買</p>\n'
                '<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">• 運行時請勿操作滑鼠</p>\n'
                '<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">• 需要管理員權限</p></body></html>',
            )
        )
        self.githubText.setText(_translate("Main", "GitHub:"))
        self.githubTextUrl.setText(
            _translate(
                "Main",
                '<a href="https://github.com/LUMR/epic7autoBookmark">https://github.com/LUMR/epic7autoBookmark</a>',
            )
        )
        self.tabWidget.setTabText(
            self.tabWidget.indexOf(self.introductionTab), _translate("Main", "簡介")
        )

    def startPressEvent(self) -> None:
        self.start = not self.start

        if self.start:
            self._handle_start()
        else:
            self._handle_stop()

    def _handle_start(self) -> None:
        """处理开始按钮点击。"""
        startMode = 0
        expectNum = 0

        moneyNum = (
            int(self.moneyTotalShowEdit.text())
            if self.moneyTotalShowEdit.text().isdigit()
            else 0
        )
        stoneNum = (
            int(self.stoneTotalShowEdit.text())
            if self.stoneTotalShowEdit.text().isdigit()
            else 0
        )

        # 校验金币和天空石
        if moneyNum == 0 or stoneNum == 0:
            self.logTextBrowser.setText("")
            self.logTextBrowser.append("石頭或金幣輸入錯誤")
            self.logTextBrowser.append("===== 停止 =====")
            self.start = not self.start
            self.startProperty(False)
            return

        # 解析模式
        if self.covenantRadioButton.isChecked():
            startMode = 1
            covenant = self.covenantInput.text()
            expectNum = int(covenant) if covenant.isdigit() else 0
            self.covenantInput.setText(str(expectNum))
        elif self.mysticRadioButton.isChecked():
            startMode = 2
            mystic = self.mysticInput.text()
            expectNum = int(mystic) if mystic.isdigit() else 0
            self.mysticInput.setText(str(expectNum))
        elif self.stoneRadioButton.isChecked():
            startMode = 3
            stone = self.stoneInput.text()
            expectNum = int(stone) if stone.isdigit() else 0
            expectNum = expectNum - (expectNum % 3)
            self.stoneInput.setText(str(expectNum))
        else:
            self.logTextBrowser.append("沒有選取的radioButton,")
            self.logTextBrowser.append("明明就預設會選一個,")
            self.logTextBrowser.append("你是怎麼取消掉的? 能不能教我?")
            self.logTextBrowser.append("===== 停止 =====")
            self.start = not self.start
            self.startProperty(False)
            return

        # Bug #6 修复：expectNum == 0 时提示用户
        if expectNum == 0:
            self.logTextBrowser.setText("")
            self.logTextBrowser.append("請輸入有效的次數或數量")
            self.logTextBrowser.append("===== 停止 =====")
            self.start = not self.start
            self.startProperty(False)
            return

        self.worker.setVariable(startMode, expectNum, moneyNum, stoneNum)
        self.worker.start()

    def _handle_stop(self) -> None:
        """处理停止按钮点击。使用 worker.stop() 替代 terminate()。"""
        self.worker.stop()       # Bug #3 修复：优雅停止
        self.worker.wait(5000)
        self.logTextBrowser.append("===== 停止 =====")
        self.startProperty(False)

    def startProperty(self, isDisabled: bool) -> None:
        if isDisabled:
            self.startButton.setText("停止")
        else:
            self.startButton.setText("開始")

        self.covenantRadioButton.setDisabled(isDisabled)
        self.mysticRadioButton.setDisabled(isDisabled)
        self.stoneRadioButton.setDisabled(isDisabled)
        self.moneyTotalShowEdit.setDisabled(isDisabled)
        self.stoneTotalShowEdit.setDisabled(isDisabled)
        self.covenantInput.setDisabled(isDisabled)
        self.mysticInput.setDisabled(isDisabled)
        self.stoneInput.setDisabled(isDisabled)

    def startWorker(self) -> None:
        self.logTextBrowser.setText("")
        self.startProperty(True)

    def errorWorker(self) -> None:
        self.start = False
        self.startProperty(False)

    def stopWorker(self) -> None:
        self.start = False
        self.startProperty(False)
