import QtQml
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: window
    width: 640
    height: 480
    visible: true
    title: "Kirigami krest Example"

    pageStack.initialPage: mainPage

    Component {
        id: mainPage

        Kirigami.Page {
            title: "Home"

            ColumnLayout {
                anchors.centerIn: parent
                spacing: Kirigami.Units.largeSpacing

                Kirigami.Heading {
                    text: "Welcome to Kirigami"
                    level: 1
                }

                // This is a basic button using Text + MouseArea
                Rectangle {
                    color: Kirigami.Theme.highlightColor
                    radius: 4
                    width: 150
                    height: 40

                    Text {
                        anchors.centerIn: parent
                        text: "Go to About"
                        color: Kirigami.Theme.highlightedTextColor
                    }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: pageStack.push(aboutPage)
                        cursorShape: Qt.PointingHandCursor
                    }
                }
            }
        }
    }

    Component {
        id: aboutPage

        Kirigami.Page {
            title: "About"

            ColumnLayout {
                anchors.centerIn: parent
                spacing: Kirigami.Units.largeSpacing

                Kirigami.Heading {
                    text: "About This App"
                    level: 2
                }

                Text {
                    text: "This is a simple app built with Kirigami and Python using krest."
                    wrapMode: Text.WordWrap
                    Layout.preferredWidth: parent.width * 0.8
                }

                Rectangle {
                    color: Kirigami.Theme.highlightColor
                    radius: 4
                    width: 100
                    height: 36

                    Text {
                        anchors.centerIn: parent
                        text: "Back"
                        color: Kirigami.Theme.highlightedTextColor
                    }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: pageStack.pop()
                        cursorShape: Qt.PointingHandCursor
                    }
                }
            }
        }
    }
}


/*
Kirigami.ApplicationWindow {
    id: root

    title: qsTr("KREST")

    minimumWidth: Kirigami.Units.gridUnit * 20
    minimumHeight: Kirigami.Units.gridUnit * 20
    width: minimumWidth
    height: minimumHeight

    pageStack.initialPage: initPage

    Component {
        id: initPage

        Kirigami.Page {
            title: qsTr("Markdown Viewer")

            ColumnLayout {
                anchors {
                    top: parent.top
                    left: parent.left
                    right: parent.right
                }
                Controls.TextArea {
                    id: sourceArea

                    placeholderText: qsTr("Write some Markdown code here")
                    wrapMode: Text.WrapAnywhere
                    Layout.fillWidth: true
                    Layout.minimumHeight: Kirigami.Units.gridUnit * 5 
                }

                RowLayout {
                    Layout.fillWidth: true

                    Controls.Button {
                        text: qsTr("Format")

                        onClicked: formattedText.text = sourceArea.text
                    }

                    Controls.Button {
                        text: qsTr("Clear")

                        onClicked: {
                            sourceArea.text = ""
                            formattedText.text = ""
                        }
                    }
                } 

                Text {
                    id: formattedText

                    textFormat: Text.RichText
                    wrapMode: Text.WordWrap
                    text: sourceArea.text

                    Layout.fillWidth: true
                    Layout.minimumHeight: Kirigami.Units.gridUnit * 5
                }
            }
    	}


    }




/*

    pageStack.initialPage: Kirigami.Page {

        Kirigami.AboutDialog {
            id: aboutDialog
            title: i18n("About KREST")
            icon.name: "krest"
            version: "1.0.0"
            description: i18n("KREST is a simple application to call REST endpoints.")
            licenseText: i18n("This software is licensed under the GNU General Public License v2.")
        }

        Controls.Label {
            anchors.centerIn: parent
            text: i18n("KREST - call REST endpoints with Faith")
            font.pointSize: 25
        }

        actions: [

            Kirigami.Action {
                text: i18n("About")
                icon.name: "help-about"
                onTriggered: Kirigami.AboutDialog.open()
            },
            
            Kirigami.Action {
                text: i18n("Quit")
                icon.name: "application-exit-symbolic"
                shortcut: StandardKey.Quit
                onTriggered: Qt.quit()
            }
        ]

    }
    
}

*/