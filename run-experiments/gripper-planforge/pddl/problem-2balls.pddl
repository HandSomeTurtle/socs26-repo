(define (problem gripper-2balls)
  (:domain gripper-small)
  (:objects
    rooma roomb - room
    ball1 ball2 - ball
    left right - gripper
  )
  (:init
    (at-robby rooma)
    (at ball1 rooma)
    (at ball2 rooma)
    (free left)
    (free right)
    (connected rooma roomb)
    (connected roomb rooma)
  )
  (:goal (and (at ball1 roomb) (at ball2 roomb)))
)
