
from random import randrange, uniform

import sys, os, datetime
import math
from Obstacle import *
from Ray import *
from World import *
import pygame
from Queue import Queue
from collections import defaultdict
import multiprocessing
from multiprocessing  import Process, Manager, Value, Array

import signal

def signal_handler(signum, frame):
	raise Exception( "Timed Out!!!" );

class DistSample:
	"""Sample with distance to obstacles.
	A dist sample can be viewed as a sphere in Rn space"""
	def __init__(self, x, y, radius):
		self.mSample = (x,y)
		self.mRadius = radius;

	def getBoundaryConfigs(self, num=0):
		""" Get configs in the boundary of the sphere. For 2D only!!!!
		@param num: the number of boundary configs you need. 
		When num = 0, automatically get boundary configs.
		"""
		retSet = []
		if( num == 0 ):
			num = self.mRadius / 5 + 5;

		dlt_ang = (2*math.pi) / float(num); # increment of angle;
		for i in range(1, int(num)+1):
			ang = dlt_ang * i;
			newX = self.mSample[0]+(self.mRadius+1.3)*math.cos( ang );
			newY = self.mSample[1]+(self.mRadius+1.3)*math.sin( ang );
			retSet += [ (newX, newY) ]
		return retSet;


	def withInArea(self, x, y):
		dx = x - self.mSample[0];
		dy = y - self.mSample[1];
		dist = math.sqrt( dx**2 + dy**2 );

		if dist < math.fabs( self.mRadius ):
			return True;
		else:
			return False;		

class SampleManager:
    def __init__( self, world ):
        self.mWorld = world;
        self.mObstMgr = world.mObstMgr;
        #self.mDistSamples = Manager().list();
        self.mDistSamples = [];
        self.mFreeSamples = [];
        self.mObstSamples = [];
        self.g_failTimes = Value( 'i', 0 );


    def simpleSample(self, num):
        """randomly sample the world. save all samples"""
        samp = [];
        sampCount = 0;
        for i in range( 0, num ):
            irand_1 = randrange(0, self.mWorld.mWidth);
            irang_2 = randrange(0, self.mWorld.mHeight);
            if not self.mObstMgr.isConfigInObstacle( (irand_1, irang_2) ):
                self.mFreeSamples += [(irand_1, irang_2)];
            else:
                self.mObstSamples += [(irand_1, irang_2)];
        pass;

    def sampleFree(self, num):
        """Sample free space only, return num samples"""
        freeSamp = [];
        freeSampCount = 0;
        while( freeSampCount < num ):
            irand_1 = randrange(0, self.mWorld.mWidth);
            irang_2 = randrange(0, self.mWorld.mHeight);
            if not self.mObstMgr.isConfigInObstacle( (irand_1, irang_2) ):
                freeSamp += [(irand_1, irang_2)];
                freeSampCount += 1;
        self.mFreeSamples = freeSamp;
        print "Finished sampling free space, got {0} samples!".format( len(freeSamp) );
        return freeSamp;

    def sampleNonVisArea( self, num ):
        """After sampling many configurations with distance info. 
        There is still space not covered by those (hyper-)spheres.
        This method samples in the non-visiable area, and get num samples"""
        if len(self.mDistSamples) == 0:
            raise Exception( "Please sample (hyper)spheres in configuration space first." );

        samples = [];
        sampCount = 0;
        while( sampCount < num ):
            irand_1 = randrange(0, self.mWorld.mWidth);
            irang_2 = randrange(0, self.mWorld.mHeight);
            newSamp = ( irand_1, irang_2 );
            newSampValid = True;
            for distSamp in self.mDistSamples:
                if distSamp.withInArea( newSamp[0], newSamp[1] ):
                    newSampValid = False;
                    break;
            if newSampValid:
                samples += [newSamp];
                sampCount += 1;

        return samples;


    def sampleObst(self, num):
        """Sample obstacle space only, return num samples"""
        obstSamp = [];
        obstSampCount = 0;
        while( obstSampCount < num ):
            irand_1 = randrange(0, self.mWorld.mWidth);
            irang_2 = randrange(0, self.mWorld.mHeight);
            if self.mObstMgr.isConfigInObstacle( (irand_1, irang_2) ):
                obstSamp += [(irand_1, irang_2)];
                obstSampCount += 1;

        self.mObstSamples = obstSamp;
        return obstSamp;

    def getARandomFreeSample(self, num):
        """Randomly sample the space and return a free sample (with distance info).
        The sample is not inside of any other sphere. Also, this method will not automatically 
        add the new sample to self.mDistSamples list.
        @param num: fail time. If failed to find such a sample num times, return null"""
        failTime=0;
        while( failTime < num ):
            rnd1 = randrange(0,self.mWorld.mWidth);
            rnd2 = randrange(0,self.mWorld.mHeight);
            if( self.mObstMgr.isConfigInObstacle( (rnd1, rnd2) ) ):
                continue;

            newSamp = True;
            for sample in self.mDistSamples:
                if sample.withInArea( rnd1, rnd2 ):
                    newSamp = False;
                    failTime += 1
                    break;
            if newSamp:
                # randomly shoot rays to get the nearest distance to obstacles
                rayShooter = RayShooter( rnd1, rnd2, self.mObstMgr );
                dist = rayShooter.randShoot(72);
                if math.fabs(dist) >= 1.0:
                    newDistSamp = DistSample(rnd1, rnd2, dist);
                    #(self.mDistSamples).append( newDistSamp );
                    print "failed times: {0}".format( failTime );
                    failTime=0;
                    return newDistSamp;
                else:
                    failTime += 1;

        return None;


    ###=======================================================================================
    ###===== Strategy 1: Randomly sample spheres
    def timeSafeSampleWithDistance( self, num, timeout ):
        """Randomly sample configurations in the c-space
        @param num: termination conditon. num times failed to find a new point, then terminate.
        @param timeout: maximun sampling time
        """
        signal.signal( signal.SIGALRM, signal_handler );
        signal.alarm( timeout );
        try:
            self.sampleWithMoreInfo( num );
        except Exception, msg:
            print msg;
            print "Get {0} samples with distances\n".format( len(self.mDistSamples) );

    def sampleWithDistInfo_multiThread(self, num):
        """Randomly sample configurations in the c-space with multi-threading
        @param num: termination conditon. num times failed to find a new point, then terminate.
        """
        try:
            self.g_failTimes.value = 0;
            threads = [];
            threadsCount = 4;
            for i in range(0,threadsCount):
                newThread = Process( target=self.__mltithreadDistSample__, args=[ i,num ] );
                threads += [newThread];
            for i in range( 0,threadsCount ):
                threads[i].start();
            for i in range( 0,threadsCount ):
                threads[i].join();

            print "Get {0} samples".format( len(self.mDistSamples) );

        except Exception, msg:
            print "Failed to start a thread, MSG:\n\t" + msg;
            self.g_failTimes.value = 0;

    def __mltithreadDistSample__(self, threadname, num):
        while( self.g_failTimes.value < num ):
            #print "Thread:\t{0} failedTimes:\t{1}\n".format( threadname, self.g_failTimes );
            rnd1 = randrange(0,self.mWorld.mWidth);
            rnd2 = randrange(0,self.mWorld.mHeight);

            newSamp = True;
            for sample in self.mDistSamples:
                if sample.withInArea( rnd1, rnd2 ):
                    newSamp = False;
                    self.g_failTimes.value += 1
                    break;

            if newSamp:
                # randomly shoot rays to get the nearest distance to obstacles
                rayShooter = RayShooter( rnd1, rnd2, self.mObstMgr );
                dist = rayShooter.randShoot(72);
                if math.fabs(dist) >= 1.0:
                    newDistSamp = DistSample(rnd1, rnd2, dist)
                    for samp in self.mDistSamples:
                        # Check if old sample is with the area of the new sample;
                        if newDistSamp.withInArea( samp.mSample[0], samp.mSample[1] ):
                            try:
                                self.mDistSamples.remove( samp );
                            except:
                                continue;
                    (self.mDistSamples) += [ newDistSamp ];
                    self.g_failTimes.value=0;

        #print "Get {0} samples in thread {1}".format( len(self.mDistSamples), threadname );


    def sampleWithMoreInfo(self, num):
        """Randomly sample configurations in the c-space
        @param num: termination conditon. num times failed to find a new point, then terminate.
        """
        failTimes = 0;
        self.mDistSamples = []
        while( failTimes < num ):
            rnd1 = randrange(0,self.mWorld.mWidth);
            rnd2 = randrange(0,self.mWorld.mHeight);

            newSamp = True;
            for sample in self.mDistSamples:
                if sample.withInArea( rnd1, rnd2 ):
                    newSamp = False;
                    failTimes += 1
                    break;

            if newSamp:
                # randomly shoot rays to get the nearest distance to obstacles
                rayShooter = RayShooter( rnd1, rnd2, self.mObstMgr );
                dist = rayShooter.randShoot(72);
                if math.fabs(dist) >= 1.0:
                    self.mDistSamples += [ DistSample(rnd1, rnd2, dist) ];
                    failTimes=0;

        print "Get {0} samples".format( len(self.mDistSamples) );
        pass

    ###=======================================================================================
    ###=== Strategy 2: Randomly sample one sphere, then sample from the boundary
    ###===         Then keep sampling the new boundary of the set of spheres
    def sampleWithDistInfo_boundStrat_multiThread(self, num):
        """Randomly sample one configuration in the c-space first. (Get a sphere)
        Then add the sphere to result set.
        repeat:
	        sample the boundary of spheres set.
	        add new sphere to the set
        until 

        @param num: Total number of spheres as a terminate condition.                     ###################### TODO: find a terminate condition that can be used to evaluate sphere coverage
        """
        try:
            #self.mDistSamples = Manager().list();
            self.g_failTimes.value = 0;
            boundaryQueue = multiprocessing.Queue();
            dictProxy = Manager().list()
            dictProxy.append({});

            threads = [];
            threadsCount = 1;
            for i in range(0,threadsCount):
                newThread = Process( target=self.__mltithreadDistSample_boundStrat__, args=[ i, dictProxy, boundaryQueue,num ] );
                threads += [newThread];
            for i in range( 0,threadsCount ):
                threads[i].start();
            for i in range( 0,threadsCount ):
                threads[i].join();

            print "Get {0} samples".format( len(self.mDistSamples) );

        except Exception, msg:
            print "Failed to start a thread, MSG:\n\t" + str(msg);
            self.g_failTimes.value = 0;

    def distSampleOneThread( self, num ):
        self.mDistSamples = [];
        boundaryQueue = Queue();
        bndSphDict = defaultdict();

        randFreeSamp = 1234;
        while( randFreeSamp != None ):
            randFreeSamp = self.getARandomFreeSample( num );
            if( randFreeSamp == None ):
                return;
            print "Size of dist samples {0}".format( len( self.mDistSamples ) );
            self.mDistSamples.append( randFreeSamp );
            bounds = randFreeSamp.getBoundaryConfigs();

            for bndConfig in bounds:
                #if not bndConfig in bndSphDict:				# put the boundconfig-sphere relation to the dictionary
                bndSphDict[bndConfig] = randFreeSamp;
                boundaryQueue.put( bndConfig );				# put the boundary config to the queue.

            while( not boundaryQueue.empty() ):
                print "Size of dist samples {0}".format( len( self.mDistSamples ) );
                if( len(self.mDistSamples) % 100 == 0 ):
                    randFreeSamp = self.getARandomFreeSample( num );
                    if( randFreeSamp == None ):
                        return;
                    (self.mDistSamples).append( randFreeSamp )
                    bounds = randFreeSamp.getBoundaryConfigs();		# get the boundary configs
                    for bndConfig in bounds:
                        #if not bndConfig in bndSphDict:				# put the boundconfig-sphere relation to the dictionary
                        bndSphDict[bndConfig] = newDistSamp;
                        boundaryQueue.put( bndConfig );				# put the boundary config to the queue.


                bnd = boundaryQueue.get();							# get a new boundary 
                newSamp = True;
                for sample in self.mDistSamples:
                    if sample.withInArea( bnd[0], bnd[1] ):
                        # check if within any spheres, not including the sphere that the boundary config belongs to.
                        newSamp = False;
                        break;

                if newSamp:
                    # randomly shoot rays to get the nearest distance to obstacles
                    rayShooter = RayShooter( bnd[0], bnd[1], self.mObstMgr );	# Shot ray
                    dist = rayShooter.randShoot(72);					# Get the distance to obstacles
                    if math.fabs(dist) >= 1.0:							# if not too close to obstacles
                        newDistSamp = DistSample(bnd[0], bnd[1], dist)	# construct a new dist sample
                        (self.mDistSamples).append( newDistSamp );				# add to our dist sample set
                        bounds = newDistSamp.getBoundaryConfigs();		# get the boundary configs
                        for bndConfig in bounds:						
                            #if not bndConfig in bndSphDict:				# put the boundconfig-sphere relation to the dictionary
                            bndSphDict[bndConfig] = newDistSamp;
                            boundaryQueue.put( bndConfig );				# put the boundary config to the queue.


    def __mltithreadDistSample_boundStrat__(self, threadname, proxy, boundaryQueue, num):
        """@param proxy: a proxy with a boundary-sphere dictionary as the first element. indicates a boundary belongs to a sphere.
         @param boundaryQueue: Queue of boundary configs
         @param num: terminate condition.
         """
        bndSphDict = proxy[0];

        """
		getALegalSample = False;
		while( not getALegalSample ):
			randSamp = ( randrange(0,self.mWorld.mWidth), randrange(0,self.mWorld.mHeight) );
			if not self.mObstMgr.isConfigInObstacle( (randSamp[0], randSamp[1]) ):
				getALegalSample = True;
				# randomly shoot rays to get the nearest distance to obstacles
				rayShooter = RayShooter( randSamp[0], randSamp[1], self.mObstMgr );
				dist = rayShooter.randShoot(72);
				if math.fabs(dist) >= 1.0:						# if not too close to obstacles
					newSamp = DistSample(randSamp[0], randSamp[1], dist);# it is considered as a new dist sample (a new sphere)
					self.mDistSamples += [ newSamp ];			# add it to our dist sample set
					bounds = newSamp.getBoundaryConfigs();		# get configs in the boundary of the sphere.
					for bndConfig in bounds:
						if not bndConfig in bndSphDict:			# add config-sphere relationship info
							bndSphDict[bndConfig] = newSamp;
						boundaryQueue.put( bndConfig );			# put the boundary config to the queue
		"""

        randFreeSamp = 1234;
        while( randFreeSamp != None ):
            print "Size of samples {0}".format( len( self.mDistSamples ) );
            randFreeSamp = self.getARandomFreeSample( num );
            if( randFreeSamp == None ):
                return
            self.mDistSamples.append( randFreeSamp );
            bounds = randFreeSamp.getBoundaryConfigs();

            for bndConfig in bounds:						
                #if not bndConfig in bndSphDict:				# put the boundconfig-sphere relation to the dictionary
                bndSphDict[bndConfig] = randFreeSamp;
                boundaryQueue.put( bndConfig );				# put the boundary config to the queue.

            while( not boundaryQueue.empty() ):
                if( self.getARandomFreeSample( num ) == None ):
                    return;
                bnd = boundaryQueue.get();							# get a new boundary 
                newSamp = True;
                for sample in self.mDistSamples:
                    if sample.withInArea( bnd[0], bnd[1] ):
                        # check if within any spheres, not including the sphere that the boundary config belongs to.
                        newSamp = False;
                        break;

                if newSamp:
                    # randomly shoot rays to get the nearest distance to obstacles
                    rayShooter = RayShooter( bnd[0], bnd[1], self.mObstMgr );	# Shot ray
                    dist = rayShooter.randShoot(72);					# Get the distance to obstacles
                    if math.fabs(dist) >= 1.0:							# if not too close to obstacles
                        newDistSamp = DistSample(bnd[0], bnd[1], dist)	# construct a new dist sample
                        (self.mDistSamples).append( newDistSamp );				# add to our dist sample set
                        bounds = newDistSamp.getBoundaryConfigs();		# get the boundary configs
                        for bndConfig in bounds:
                            #if not bndConfig in bndSphDict:				# put the boundconfig-sphere relation to the dictionary
                            bndSphDict[bndConfig] = newDistSamp;
                            boundaryQueue.put( bndConfig );				# put the boundary config to the queue.
            #randFreeSamp = self.getARandomFreeSample( num );


    def renderDistSample(self, ImgSurface):
        """Render distance sample to image"""
        print "render {0} dist samples to the image".format( len(self.mDistSamples) );
        freeColor = ( 0, 0, 250 );
        obstColor = ( 200, 0, 100 );
        for samp in self.mDistSamples:
            if samp.mRadius > 0: # Free sample
                pygame.draw.circle( ImgSurface, freeColor, (int(samp.mSample[0]), int(samp.mSample[1])), int(math.fabs(samp.mRadius)), 1 );
            else:
                pygame.draw.circle( ImgSurface, obstColor, (int(samp.mSample[0]), int(samp.mSample[1])), int(math.fabs(samp.mRadius)), 1 );

    def writeSamplesToFile( self, filename ):
        file2write = open( filename, 'w' );
        formattedData = ""
        for vector in self.mDistSamples:
            formattedData += "{0}\t{1}\t{2}\n".format( vector.mSample[0], vector.mSample[1], vector.mRadius )
            pass

        file2write.write( formattedData );
        file2write.close();


    def loadDistSamplesFromFile( self, filename ):
        file2read = open( filename, 'r' );
        self.mDistSamples = [];
        for line in file2read:
            strDistSamp = line;
            info = strDistSamp.split( '\t' );
            distSamp = DistSample( float(info[0]), float(info[1]), float(info[2]));
            if( distSamp.mRadius > 2 ):
                self.mDistSamples += [ distSamp ];