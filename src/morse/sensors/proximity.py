import GameLogic
import morse.helpers.object

class ProximitySensorClass(morse.helpers.object.MorseObjectClass):
	""" Distance sensor to detect nearby robots """

	def __init__(self, obj, parent=None):
		""" Constructor method.

		Receives the reference to the Blender object.
		The second parameter should be the name of the object's parent.
		"""
		print ("######## PROXIMITY '%s' INITIALIZING ########" % obj.name)
		# Call the constructor of the parent class
		super(self.__class__,self).__init__(obj, parent)

		self.local_data['near_robots'] = {}
		try:
			self.range = self.blender_obj['Range']
		except KeyError:
			# Set a default range of 100m
			self.range = 100
			

		print ('######## PROXIMITY INITIALIZED ########')


	def default_action(self):
		""" Create a list of robots within a certain radius of the sensor. """

		self.local_data['near_robots'] = {}

		parent = self.blender_obj.robot_parent

		# Get the fire sources
		for robot in GameLogic.robotDict.keys():
			# Skip distance to self
			if parent != robot:
				distance = self.measure_distance_to_robot (parent.blender_obj, robot.blender_obj)
				if distance <= self.range:
					self.local_data['near_robots'][robot.blender_obj.name] = distance



	def measure_distance_to_robot(own_robot, target_robot):
		""" Compute the distance between two robots

		Parameters are two blender objects
		"""
		distance, globalVector, localVector = own_robot.getVectTo(target_robot)
		#print ("Distance from robot {0} to robot {1} = {2}".format(own_robot, target_robot, distance))
		return distance
