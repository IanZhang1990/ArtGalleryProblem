
from random import randrange, uniform

import sys, os, datetime
import math
from Ray import *
from CSpaceWorld import *
from SpacePartition import *;
from ObstSurfSearcher import *
#import pygame
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
    def __init__(self, pos, radius):
        self.mSample = pos
        self.mRadius = radius;
        self.mBoundaries = None;

    def render(self, imgSurf, color):
        pygame.draw.circle( imgSurf, color, (int(self.mSample[0]),int(self.mSample[1]) ), int(self.mRadius), 1 );

    def getBoundaryConfigs(self, num=0):
        """ Get configs in the boundary of the sphere.
         @param num: the number of boundary configs you need.
         When num = 0, automatically get boundary configs."""
        if self.mRadius < 5:
            return [];

        if self.mBoundaries is not None:
            return self.mBoundaries;

        if num == 0:
            num == 10 + 10*self.mRadius;
        
        dlt_ang = (2*math.pi) / float(num); # increment of angle;
        bndRadius = self.mRadius + 1;
        for i in range(1, int(num)+1):
            ang = dlt_ang * i;
            bndx = self.mSample[0]+(bndRadius)*math.cos( ang );
            bndy = self.mSample[1]+(bndRadius)*math.sin( ang );
            self.mBoundaries.append((bndx, bndy));

        return bnds;
    
    def isInside(self, point):
        """Determine if a 2D-point is inside the sphere"""
        distSqr = (point[0]-self.mSample[0])**2 + (point[1]-self.mSample[1])**2;

        if distSqr < ( self.mRadius**2 ):
            return True;
        else:
            return False;

class SampleManager:
    def __init__( self, CSpace ):
        self.mCSpace = CSpace;
        self.mCollisionMgr = CSpace.mCollisionMgr;
        self.mDistSamples = Manager().list();
        self.mFreeSamples = [];
        self.mObstSamples = [];
        self.g_failTimes = Value( 'i', 0 );
        unitLens = [100] * len( self.mCSpace.mMaxDimLens )
        self.mSpacePartition = SpacePartition( self.mCSpace.mMaxDimLens, unitLens );

    def getFreeSamples( self, num, dim, maxDimLens ):
        """get num number of free samples in C-Space"""
        size = 0; 
        while size < num:
            rnd = [0] * dim;
            for i in range( 0, dim ):
                rnd[i] = randrange( 0, maxDimLens[i] );
                pass
            #angles = self.mCSpace.map2UnscaledSpace( rnd );
            if( not self.mCollisionMgr.ifCollide( rnd ) ):
                self.mFreeSamples.append( rnd );
                size += 1;

    def randomSample( self, num, dim, maxDimLens ):
        for i in range( 0, num ):
            rnd = [0] * dim;
            for i in range( 0, dim ):
                rnd[i] = randrange( 0, maxDimLens[i] );
                pass
            #config = self.mCSpace.map2UnscaledSpace( rnd );
            if( not self.mCollisionMgr.ifCollide( rnd ) ):
                self.mFreeSamples.append( rnd );
            else:
                self.mObstSamples.append( rnd );
     
    def getARandomFreeSample(self, num, maxDimLens, dim):
        """Randomly sample the space and return a free sample (with distance info).
         The sample is not inside of any other sphere. Also, this method will not automatically 
         add the new sample to self.mDistSamples list.
         @param num: fail time. If failed to find such a sample num times, return null"""
        failTime=0;
        while( failTime < num ):
            rnd = [0] * dim;
            for i in range( 0, dim ):
                rnd[i] = randrange( 0, maxDimLens[i] );
                pass
            #angles = self.mCSpace.map2UnscaledSpace( rnd );
            if( self.mCollisionMgr.ifCollide( rnd ) ):
                continue;

            newSamp = True;

            grid = self.mSpacePartition.getContainingGrid( rnd );
            for sphere in grid.mContainer:
                if sphere.isInside( rnd ):
                    newSamp = False;
                    failTime += 1
                    break;

            if newSamp:
                # randomly shoot rays to get the nearest distance to obstacles
                rayShooter = RayShooter( rnd, self.mCollisionMgr, self.mCSpace );
                dist = rayShooter.randShoot(50 * 2);
                if math.fabs(dist) >= 1.0:
                    newDistSamp = DistSample( rnd, dist );
                    print "------>\tfailed times: {0}".format( failTime );
                    failTime=0;
                    return newDistSamp;
                else:
                    failTime += 1;

        return None;
           

    def distSampleUsingObstSurfSamps( self, num, maxDimLens ):
        """@param num: failure time to sample a new configuration randomly"""

        self.randomSample( 100, len(maxDimLens), maxDimLens );
        searcher = ObstSurfSearcher(self.mCollisionMgr, self.mCSpace);
        searcher.searchObstSurfConfigs( self.mFreeSamples, self.mObstSamples, 2 );

        self.mDistSamples = [];
        boundaryQueue = [];
        bndSphDict = defaultdict();
        randFreeSamp = 1234;

        while( randFreeSamp != None ):
            randFreeSamp = self.getARandomFreeSample( num, maxDimLens, 2);
            if( randFreeSamp == None ):
                return;
            self.mDistSamples.append( randFreeSamp );
            bounds = randFreeSamp.getBoundaryConfigs( maxDimLens );

            for bndConfig in bounds:
                #if not bndConfig in bndSphDict:			# put the boundconfig-sphere relation to the dictionary
                bndSphDict[str(bndConfig)] = randFreeSamp;
                boundaryQueue.append( bndConfig );				# put the boundary config to the queue.

            while( len( boundaryQueue) != 0 ):
                bnd = boundaryQueue[0];							# get a new boundary
                del boundaryQueue[0]
                newSamp = True;
                bndUnscaled = self.mCSpace.map2UnscaledSpace( bnd );
                if self.mCollisionMgr.ifCollide( bndUnscaled ):
                    continue;

                grid = self.mSpacePartition.getContainingGrid( bnd );
                for sphere in grid.mContainer:
                    if sphere.isInside( bnd, maxDimLens ):
                        newSamp = False;
                        break;

                if newSamp:
                    # get the nearest distance to obstacles
                    dist, neighbor = searcher.getNearest( bnd );              # Get the distance to obstacles
                    if (dist) >= 30.0:	    					 # if not too close to obstacles
                        newDistSamp = DistSample(bnd, dist)	# construct a new dist sample
                        print "{0}  R: {1}".format( bnd, dist );
                        self.mDistSamples.append( newDistSamp );				# add to our dist sample set
                        self.mSpacePartition.addSphere( newDistSamp );         ############# Add new sphere to space partition
                        #if( len(self.mDistSamples) >= 800 ):
                        #    return;
                        bounds = newDistSamp.getBoundaryConfigs(maxDimLens);		# get the boundary configs
                        for bndConfig in bounds:
                            #if not bndConfig in bndSphDict:				# put the boundconfig-sphere relation to the dictionary
                            bndSphDict[str(bndConfig)] = newDistSamp;
                            boundaryQueue.append( bndConfig );				# put the boundary config to the queue.
                        
                        ###########################=========================================================
                        if len(self.mDistSamples)%30 == 0:
                            print "------------ FRESH -------------"
                            idx = 0;
                            for bnd in boundaryQueue:
                                grid = self.mSpacePartition.getContainingGrid( bnd );
                                for sphere in grid.mContainer:
                                    if sphere.isInside( bnd, maxDimLens ):
                                        del boundaryQueue[idx];
                                        idx -= 1;
                                idx += 1;

                        #    for sphere in self.mDistSamples:
                        #        boundaryQueue = [x for x in boundaryQueue if( not sphere.isInside(x, maxDimLens)) ]
                        ###########################=========================================================

                        print "\t\t\t\t\t\t\t\t\t\t{0}\n".format(len(boundaryQueue));



    def distSampleOneThread( self, num, maxDimLens ):
        """@param num: failure time to sample a new configuration randomly"""

        self.mDistSamples = [];
        boundaryQueue = [];
        bndSphDict = defaultdict();

        randFreeSamp = 1234;
        while( randFreeSamp != None ):
            randFreeSamp = self.getARandomFreeSample( num, maxDimLens, len(maxDimLens) );
            if( randFreeSamp == None ):
                return;
            self.mDistSamples.append( randFreeSamp );
            bounds = randFreeSamp.getBoundaryConfigs( maxDimLens );

            for bndConfig in bounds:
                #if not bndConfig in bndSphDict:			# put the boundconfig-sphere relation to the dictionary
                bndSphDict[str(bndConfig)] = randFreeSamp;
                boundaryQueue.append( bndConfig );				# put the boundary config to the queue.

            while( len( boundaryQueue) != 0 ):
                bnd = boundaryQueue[0];							# get a new boundary
                del boundaryQueue[0]
                newSamp = True;
                if self.mCollisionMgr.ifCollide( bnd ):
                    continue;
                for sample in self.mDistSamples:
                    if sample.isInside( bnd, maxDimLens ): #####################################################################################================================ Locally Sensetive Hash
                        # check if within any spheres, not including the sphere that the boundary config belongs to.
                        newSamp = False;
                        break;

                if newSamp:
                    # randomly shoot rays to get the nearest distance to obstacles
                    rayShooter = RayShooter( bnd, self.mCollisionMgr, self.mCSpace );	# Shot ray
                    dim = len(maxDimLens);
                    dist = rayShooter.randShoot(50*(dim-1));					# Get the distance to obstacles
                    if (dist) >= 40.0:	    					# if not too close to obstacles
                        newDistSamp = DistSample(bnd, dist)	# construct a new dist sample
                        print "{0}  R: {1}".format( bnd, dist );
                        self.mDistSamples.append( newDistSamp );				# add to our dist sample set
                        bounds = newDistSamp.getBoundaryConfigs(maxDimLens);		# get the boundary configs
                        if len(self.mDistSamples) == 100:
                            return;
                        for bndConfig in bounds:
                            #if not bndConfig in bndSphDict:				# put the boundconfig-sphere relation to the dictionary
                            bndSphDict[str(bndConfig)] = newDistSamp;
                            boundaryQueue.append( bndConfig );				# put the boundary config to the queue.
                        
                        ###########################=========================================================
                        if len(self.mDistSamples)%100 == 0:
                            print "------------ FRESH -------------"
                            for sphere in self.mDistSamples:
                                boundaryQueue = [x for x in boundaryQueue if( not sphere.isInside(x, maxDimLens)) ]
                        ###########################=========================================================

                        print "\t\t\t\t\t\t\t\t\t{0}\n".format(len(boundaryQueue));
                        

    def writeSamplesToFile( self, filename ):
        file2write = open( filename, 'w' );
        formattedData = ""
        for vector in self.mDistSamples:
            for i in range( 0, len(vector.mSample) ):
                formattedData += str( vector.mSample[i] ) + "\t";
            formattedData += str(vector.mRadius);
            formattedData += "\n";
            pass
        
        file2write.write( formattedData );
        file2write.close();

    def loadDistSamplesFromFile( self, filename ):
        file2read = open( filename, 'r' );
        self.mDistSamples = [];
        lineNum = 0;
        for line in file2read:
            if( lineNum % 100 == 0 ):
                print "Reading line: {0}".format( lineNum );
            lineNum += 1;
            strDistSamp = line;
            info = strDistSamp.split( '\t' );
            dim = len(info);
            pos = [0] * (dim-1);
            for i in range(0,dim-1):
                pos[i] = float( info[i] );
            radius = float(info[dim-1]);
            distSamp = DistSample(tuple(pos), radius);
            if( distSamp.mRadius >= 2 ):
                self.mDistSamples += [ distSamp ];
                self.mSpacePartition.addSphere( distSamp );

    def renderDistSamples(self, imgSurf):
        for samp in self.mDistSamples:
            samp.render( imgSurf, (0,250,0) );