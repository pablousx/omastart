import QtQuick
import QtQuick.Shapes

Item {
    id: root
    property color foreground: "white"

    Shape {
        anchors.centerIn: parent
        width: 24
        height: 24
        scale: Math.min(parent.width, parent.height) / 24
        preferredRendererType: Shape.CurveRenderer

        // A single filled outline avoids seams where the shaft meets the head.
        // Both shaft edges leave at 45 degrees and bend only toward vertical.
        ShapePath {
            strokeWidth: -1
            fillColor: root.foreground
            PathSvg {
                path: "M 6.3 15.3 C 10.1 11.5 12 7.8 12 5.5 "
                    + "L 9.2 8.3 Q 8.5 9 7.8 8.3 Q 7.1 7.6 7.8 6.9 "
                    + "L 12.3 2.4 Q 13 1.7 13.7 2.4 "
                    + "L 18.2 6.9 Q 18.9 7.6 18.2 8.3 Q 17.5 9 16.8 8.3 "
                    + "L 14 5.5 C 14 8.8 11.9 12.5 7.7 16.7 "
                    + "Q 7 17.4 6.3 16.7 Q 5.6 16 6.3 15.3 Z"
            }
        }
        ShapePath {
            strokeWidth: -1
            fillColor: root.foreground
            PathSvg { path: "M 3 19.5 H 11 A 1 1 0 0 1 11 21.5 H 3 A 1 1 0 0 1 3 19.5 Z" }
        }
    }
}
