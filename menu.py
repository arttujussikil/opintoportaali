import getpass
from course_management import *

def main():
    print("Welcome to the Course Management System")

    while True:
        print("1. Login")
        print("2. Create Course")
        print("3. Edit Course")
        print("4. View Courses")
        print("5. Reserve Spot")
        print("6. Cancel Reservation")
        print("7. Get Enrollments")
        print("8. Delete Course")
        print("9. Delete User")
        print("10. Create User")
        print("0. Exit")

        choice = input("Enter your choice: ")

        if choice == "1":
            username = input("Username: ")
            password = getpass.getpass(prompt="Password: ")

            authenticated, user = login(username, password)

            if authenticated:
                print(f"Welcome, {user.name} ({user.role_id})!")
            else:
                print("Invalid credentials")

        elif choice == "2":
            if current_user.is_authenticated and (current_user.is_teacher or current_user.is_admin):
                title = input("Title: ")
                description = input("Description: ")
                start_date = input("Start date (YYYY-MM-DD): ")
                end_date = input("End date (YYYY-MM-DD): ")
                location = input("Location: ")
                instructor = input("Instructor: ")
                spots_available = input("Spots available: ")
                start_time = input("Start time (HH:MM:SS): ")
                end_time = input("End time (HH:MM:SS): ")

                create_course(title, description, start_date, end_date, location, instructor, spots_available, start_time, end_time)
            else:
                print("You do not have permission to perform this action.")

        elif choice == "3":
            if current_user.is_authenticated and (current_user.is_teacher or current_user.is_admin):
                course_id = input("Enter the course ID to edit: ")
                title = input("Title: ")
                description = input("Description: ")
                start_date = input("Start date (YYYY-MM-DD): ")
                end_date = input("End date (YYYY-MM-DD): ")
                location = input("Location: ")
                instructor = input("Instructor: ")

                edit_course(course_id, title=title, description=description, start_date=start_date, end_date=end_date, location=location, instructor=instructor)
            else:
                print("You do not have permission to perform this action.")

        elif choice == "4":
            courses = view_courses()
            print("ID\tTitle\t\tDescription\tStart Date\tEnd Date\tLocation\tInstructor")
            for course in courses:
                print(f"{course[0]}\t{course[1]}\t{course[2]}\t{course[3]}\t{course[4]}\t{course[5]}\t{course[6]}")

        elif choice == "5":
            if current_user.is_authenticated and current_user.is_student:
                course_id = input("Enter the course ID to reserve a spot: ")
                student_id = current_user.id

                reserve_spot(course_id, student_id)
            else:
                print("You do not have permission to perform this action.")

        elif choice == "6":
            if current_user.is_authenticated and current_user.is_student:
                enrollment_id = input("Enter the enrollment ID to cancel: ")
                cancel_reservation(enrollment_id)
            else:
                print("You do not have permission to perform this action.")

        elif choice == "7":
            if current_user.is_authenticated and (current_user.is_teacher or current_user.is_admin):
                course_id = input("Enter the course ID: ")
                enrollments = get_enrollments(course_id)
                if len(enrollments) == 0:
                    print("No enrollments found for this course.")
                else:
                    print(f"Enrollments for course {course_id}:")
                    for enrollment in enrollments:
                        print(f"ID: {enrollment['id']}, Student: {enrollment['student_id']}, Course: {enrollment['course_id']}")
            else:
                print("You need to be logged in as a teacher or admin to view enrollments.")
        elif choice == "8":
            if current_user.is_authenticated and current_user.is_admin:
                course_id = input("Enter the ID of the course you want to delete: ")
                delete_course(course_id)
            else:
                print("You need to be logged in as an admin to delete a course.")

        elif choice == "9":
            if current_user.is_authenticated and current_user.is_admin:
                user_id = input("Enter the ID of the user you want to delete: ")
                delete_user(user_id)
            else:
                print("You need to be logged in as an admin to delete a user.")

        elif choice == "10":
            name = input("Enter your name: ")
            email = input("Enter your email: ")
            password = input("Enter your password: ")
            role = input("Enter your role (admin, teacher, or student): ")
            phone = input("Enter your phone number: ")
            create_user(name, email, password, role, phone)

        elif choice == "0":
            print("Thank you for using the Course Management System.")
            exit()
        else:
            print("Invalid choice. Please try again.")
main()
