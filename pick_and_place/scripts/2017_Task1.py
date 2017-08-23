#! /usr/bin/env python
from __future__ import division, print_function, absolute_import
import sys
import rospy
from pap.jaco import Jaco
from pap.manager import PickAndPlaceNode
from kinova_msgs.msg import JointAngles, PoseVelocity
from finger_sensor_msgs.msg import FingerDetect, FingerTouch
from std_msgs.msg import Header, Int32MultiArray, Bool
from geometry_msgs.msg import Pose, PoseStamped, Point, Quaternion
import numpy as np

from pap import pose_action_client
from pap import fingers_action_client
from pap import joints_action_client

import tf
import tf2_ros
import commands

class pick_peas_class(object):
    def __init__(self):
        self.j = Jaco()
        self.listener = tf.TransformListener()
        self.current_joint_angles = [0]*6

        self.tfBuffer = tf2_ros.Buffer()
        self.listen = tf2_ros.TransformListener(self.tfBuffer)

        self.velocity_pub = rospy.Publisher('/j2n6a300_driver/in/cartesian_velocity',
                                            PoseVelocity, queue_size=1)

        self.obj_det_sub = rospy.Subscriber('/finger_sensor/obj_detected',
                                            FingerDetect, self.set_obj_det)

        self.fingetouch_finger_2_sub = rospy.Subscriber('/finger_sensor/touch',
                                                 FingerTouch, self.set_touch)

        self.joint_angles_sub = rospy.Subscriber("/j2n6a300_driver/out/joint_angles",
                                                JointAngles, self.callback)

        self.calibrate_obj_det_pub = rospy.Publisher("/finger_sensor/calibrate_obj_det",
                                                    Bool,
                                                    queue_size=1)

        self.calibrate_obj_det_sub = rospy.Subscriber("/finger_sensor/obj_det_calibrated",
                                                    Bool,
                                                    self.set_calibrated)

        self.obj_det = False
        self.touch_finger_1 = False
        self.touch_finger_3 = False
        self.calibrated = False



    def set_obj_det(self,msg):
        self.obj_det = np.any(np.array([msg.finger1, msg.finger2, msg.finger3]))
        print(self.obj_det)


    def set_touch(self, msg):
        self.touch_finger_1 = msg.finger1
        self.touch_finger_3 = msg.finger3

    def callback(self,data):
        # self.current_joint_angles[0] = data.joint1
        self.current_joint_angles[1] = data.joint2
        self.current_joint_angles[2] = data.joint3
        self.current_joint_angles[3] = data.joint4
        self.current_joint_angles[4] = data.joint5
        self.current_joint_angles[5] = data.joint6
        # print (self.current_joint_angles)


    def cmmnd_CartesianPosition(self, pose_value, relative):
        pose_action_client.getcurrentCartesianCommand('j2n6a300_')
        pose_mq, pose_mdeg, pose_mrad = pose_action_client.unitParser('mq', pose_value, relative)
        poses = [float(n) for n in pose_mq]
        orientation_XYZ = pose_action_client.Quaternion2EulerXYZ(poses[3:])

        try:
            poses = [float(n) for n in pose_mq]
            result = pose_action_client.cartesian_pose_client(poses[:3], poses[3:])
        except rospy.ROSInterruptException:
            print ("program interrupted before completion")

    def cmmnd_FingerPosition(self, finger_value):
        commands.getoutput('rosrun kinova_demo fingers_action_client.py j2n6a300 percent -- {0} {1} {2}'.format(finger_value[0],finger_value[1],finger_value[2]))

    def cmmnd_CartesianVelocity(self,cart_velo):
        msg = PoseVelocity(
            twist_linear_x=cart_velo[0],
            twist_linear_y=cart_velo[1],
            twist_linear_z=cart_velo[2],
            twist_angular_x=cart_velo[3],
            twist_angular_y=cart_velo[4],
            twist_angular_z=cart_velo[5])
        self.velocity_pub.publish(msg)

    def cmmnd_JointAngles(self,joints_cmd, relative):
        joints_action_client.getcurrentJointCommand('j2n6a300_')
        joint_degree, joint_radian = joints_action_client.unitParser('degree', joints_cmd, relative)
        try:
            positions = [float(n) for n in joint_degree]
            result = joints_action_client.joint_angle_client(positions)
        except rospy.ROSInterruptException:
            print('program interrupted before completion')

    def set_calibrated(self,msg):
        self.calibrated = msg.data

    def pick_spoon(self):
        self.calibrate_obj_det_pub.publish(True)

        while self.calibrated == False:
            pass

        print("Finger Sensors calibrated")

        try:
            trans = self.tfBuffer.lookup_transform('root', 'spoon_position', rospy.Time())
        except (tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException):
            rate.sleep()
            # continue

        translation  = [trans.transform.translation.x, trans.transform.translation.y, trans.transform.translation.z]
        rotation = [trans.transform.rotation.x, trans.transform.rotation.y, trans.transform.rotation.z, trans.transform.rotation.w]
        pose_value = translation + rotation
        #second arg=0 (absolute movement), arg = '-r' (relative movement)
        self.cmmnd_CartesianPosition(pose_value, 0)


    def goto_bowl(self):
        rate = rospy.Rate(100)
        while not rospy.is_shutdown():
            try:
                trans = self.tfBuffer.lookup_transform('root', 'bowl_position', rospy.Time())
                break
            except (tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException):
                rate.sleep()

        translation  = [trans.transform.translation.x, trans.transform.translation.y, trans.transform.translation.z]
        rotation = [trans.transform.rotation.x, trans.transform.rotation.y, trans.transform.rotation.z, trans.transform.rotation.w]
        pose_value = translation + rotation
        self.cmmnd_CartesianPosition(pose_value, 0) #second arg=0 (absolute movement), arg = '-r' (relative movement)


    def goto_plate(self):
        if self.listen.frameExists("/root") and self.listen.frameExists("/plate_position1"):
            self.listen.waitForTransform('/root','/plate_position',rospy.Time(),rospy.Duration(100.0))
            print ("we have the bowl frame")
            # t1 = self.listen.getLatestCommonTime("/root", "bowl_position")
            translation, quaternion = self.listen.lookupTransform("/root", "/plate_position", rospy.Time(0))

            translation =  list(translation)
            quaternion = [0.8678189045198146, 0.0003956789257977804, -0.4968799802988633, 0.0006910675928639343]
            pose_value = translation + quaternion
            #second arg=0 (absolute movement), arg = '-r' (relative movement)
            self.cmmnd_CartesianPosition(pose_value, 0)

        else:
            print ("we DONT have the bowl frame")

    def lift_spoon(self):
        rate = rospy.Rate(100) # NOTE to publish cmmds to velocity_pub at 100Hz
        # self.move_fingercmmd([0, 0, 0])
        while self.touch_finger_3 != True:
            self.cmmnd_CartesianVelocity([0,0.025,0,0,0,0,1])
            rate.sleep()
        self.touch_finger_3 = False

        self.cmmnd_FingerPosition([100, 0, 100])
        self.cmmnd_CartesianPosition([0, 0, 0.13, 0, 0, 0, 1],'-r')
        self.cmmnd_FingerPosition([100, 100, 100])


    def searchSpoon(self):
        rate = rospy.Rate(100)
        while not rospy.is_shutdown():
            try:
                trans = self.tfBuffer.lookup_transform('root', 'j2n6a300_end_effector', rospy.Time())
                break
            except (tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException):
                rate.sleep()

        translation  = [trans.transform.translation.x, trans.transform.translation.y, trans.transform.translation.z]
        rotation = [trans.transform.rotation.x, trans.transform.rotation.y, trans.transform.rotation.z, trans.transform.rotation.w]

        matrix1 = self.listener.fromTranslationRotation(translation,rotation)
        counter = 0
        rate = rospy.Rate(100)
        while not self.obj_det and not rospy.is_shutdown():
            counter = counter + 1
            if(counter < 200):
                cart_velocities = np.dot(matrix1[:3,:3],np.array([0,0,0.05])[np.newaxis].T) #change in y->x, z->y, x->z
                cart_velocities = cart_velocities.T[0].tolist()
                self.cmmnd_CartesianVelocity(cart_velocities + [0,0,0,1])
                print("forward")
            else:
                cart_velocities = np.dot(matrix1[:3,:3],np.array([0,0,-0.05])[np.newaxis].T)
                cart_velocities = cart_velocities.T[0].tolist()
                self.cmmnd_CartesianVelocity(cart_velocities + [0,0,0,1])
                print("backwards")
            if(counter > 400):
                counter = 0
            rate.sleep()


if __name__ == '__main__':
    rospy.init_node("task_1")
    rate = rospy.Rate(100)
    p = pick_peas_class()
    p.j.home()
    p.cmmnd_FingerPosition([0, 0, 75])

    print ("Starting task. . .\n")
    p.pick_spoon()
    p.cmmnd_JointAngles([0,0,0,0,0,-15], '-r')

    print ("Searching spoon. . .\n")
    p.searchSpoon()
    p.cmmnd_CartesianPosition([0.015,0,0,0,0,0,1], '-r')

    print ("trying to touch the spoon now. . .\n")
    p.lift_spoon()

    print ("Going to bowl. . .\n")
    p.goto_bowl()
    print ("Bowl reached. . .\n")

    print ("Scooping the peas. . .")
    p.cmmnd_JointAngles([0,0,0,0,0,-25], '-r')
    p.cmmnd_CartesianPosition([0,0,-0.135,0,0,0,1], '-r')
    # p.cmmnd_CartesianPosition([0,0.04,0,0,0,0,1], '-r')
    p.cmmnd_JointAngles([0,0,0,0,0,-40], '-r')
    p.cmmnd_CartesianPosition([0,0,0.135,0,0,0,1], '-r')
    print ("scooping done. . .")

    print ("dumping in the plate. . .")
    p.cmmnd_CartesianPosition([-0.25,0.1,-0.08,0,0,0,1], '-r')
    p.cmmnd_JointAngles([0,0,0,0,0,40], '-r')
